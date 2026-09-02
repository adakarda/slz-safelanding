#!/usr/bin/env python3
"""Landing HUD -- what the pipeline sees, what it chose, and why.

Publishes a single rendered image on ``/eland/hud``. Open it with

    ros2 run rqt_image_view rqt_image_view /eland/hud

Left panel: the fused semantic ground map, north up, with the vehicle at the
centre. Overlaid on it are the two circles the site selection actually reasons
about -- the clearance the chosen site achieves, and ``r_ideal``, the radius
the detector was trying to fit. When the solid circle reaches the dashed one
the site is as open as the policy asks for; a solid circle much smaller than
the dashed one means the vehicle settled for a tighter spot.

Right panel: the numbers behind the decision. Every value here is read from a
message rather than recomputed, so the HUD cannot quietly disagree with the
controller -- ``commanded_descent_mps`` and ``descent_ceiling_mps`` are
published by the mode precisely so this panel does not have to re-derive them
and drift.

A note on the label: the descent law is a proportional controller, not a PID.
The panel says so. There is no integral term (in windless flight it only
winds up) and no derivative term (the goto setpoint's jerk-limited smoother
already provides the damping one would add it for), so printing Ki and Kd as
zero would suggest a tuning knob that is not there.
"""

import math

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Point
from nav_msgs.msg import OccupancyGrid
from px4_msgs.msg import VehicleLocalPosition
from rclpy.node import Node
from sensor_msgs.msg import Image
from eland_common import classes, px4_topics
from eland_common.qos import DECISION_QOS, PX4_QOS, SENSOR_QOS
from eland_msgs.msg import LandingCandidate, LandingState

STATE_NAMES = {
    LandingState.SEARCH: 'SEARCH',
    LandingState.APPROACH: 'APPROACH',
    LandingState.VALIDATE: 'VALIDATE',
    LandingState.HOLD: 'HOLD',
    LandingState.ABORT: 'ABORT',
    LandingState.COMMIT: 'COMMIT',
}

#: BGR, for cv2. Warm colours for the states where the vehicle is committed or
#: in trouble, so a glance at the header is enough.
STATE_COLORS = {
    LandingState.SEARCH: (200, 200, 200),
    LandingState.APPROACH: (240, 200, 90),
    LandingState.VALIDATE: (110, 220, 110),
    LandingState.HOLD: (80, 200, 250),
    LandingState.ABORT: (80, 130, 250),
    LandingState.COMMIT: (110, 110, 250),
}

FONT = cv2.FONT_HERSHEY_SIMPLEX


class HudNode(Node):
    """Ground map + decision state -> one annotated image."""

    def __init__(self) -> None:
        super().__init__('hud_node')

        self.declare_parameter('map_size_px', 520)
        self.declare_parameter('panel_width_px', 330)
        self.declare_parameter('rate_hz', 5.0)
        self.declare_parameter('r_ideal', 8.0)
        self.declare_parameter('r_hazard', 3.0)
        self.declare_parameter('descent_size_gain', 0.20)
        self.declare_parameter('descent_min_mps', 0.3)
        self.declare_parameter('descent_max_mps', 2.0)
        self.declare_parameter('map_topic', '/eland/ground_map')
        self.declare_parameter('candidate_topic', '/eland/candidate')
        self.declare_parameter('state_topic', '/eland/state')
        self.declare_parameter('hud_topic', '/eland/hud')
        self.declare_parameter(
            'vehicle_local_position_topic', px4_topics.VEHICLE_LOCAL_POSITION)

        self.map_px = int(self.get_parameter('map_size_px').value)
        self.panel_px = int(self.get_parameter('panel_width_px').value)
        self.r_ideal = float(self.get_parameter('r_ideal').value)
        self.r_hazard = float(self.get_parameter('r_hazard').value)
        self.k_size = float(self.get_parameter('descent_size_gain').value)
        self.v_min = float(self.get_parameter('descent_min_mps').value)
        self.v_max = float(self.get_parameter('descent_max_mps').value)

        self.bridge = CvBridge()
        self.palette = np.zeros((classes.NUM_CLASSES, 3), dtype=np.uint8)
        for cid, rgb in classes.CLASS_COLORS.items():
            self.palette[cid] = (rgb[2], rgb[1], rgb[0])  # cv2 is BGR

        self.grid = None
        self.map_info = None
        self.candidate = None
        self.state = None
        self.pos_enu = None
        self.vel_enu = None
        self.altitude = 0.0

        self.hud_pub = self.create_publisher(
            Image, self.get_parameter('hud_topic').value, SENSOR_QOS)
        self.create_subscription(
            OccupancyGrid, self.get_parameter('map_topic').value,
            self.on_map, SENSOR_QOS)
        self.create_subscription(
            LandingCandidate, self.get_parameter('candidate_topic').value,
            self.on_candidate, DECISION_QOS)
        self.create_subscription(
            LandingState, self.get_parameter('state_topic').value,
            self.on_state, DECISION_QOS)
        self.create_subscription(
            VehicleLocalPosition,
            self.get_parameter('vehicle_local_position_topic').value,
            self.on_local_position, PX4_QOS)

        rate = float(self.get_parameter('rate_hz').value)
        self.create_timer(1.0 / max(rate, 0.1), self.render)
        self.get_logger().info(
            f'hud_node up -> {self.get_parameter("hud_topic").value} '
            f'@ {rate:.0f} Hz. View with: '
            f'ros2 run rqt_image_view rqt_image_view '
            f'{self.get_parameter("hud_topic").value}')

    # ------------------------------------------------------------------
    def on_map(self, msg: OccupancyGrid) -> None:
        w, h = msg.info.width, msg.info.height
        if w == 0 or h == 0:
            return
        self.grid = np.clip(
            np.asarray(msg.data, dtype=np.int16).reshape(h, w),
            0, classes.NUM_CLASSES - 1).astype(np.uint8)
        self.map_info = msg.info

    def on_candidate(self, msg: LandingCandidate) -> None:
        self.candidate = msg

    def on_state(self, msg: LandingState) -> None:
        self.state = msg

    def on_local_position(self, msg: VehicleLocalPosition) -> None:
        self.pos_enu = (float(msg.y), float(msg.x), float(-msg.z))
        self.vel_enu = (float(msg.vy), float(msg.vx), float(-msg.vz))
        self.altitude = (float(msg.dist_bottom) if msg.dist_bottom_valid
                         else float(-msg.z))

    # ------------------------------------------------------------------
    def world_to_px(self, east: float, north: float):
        """ENU metres -> pixel in the rendered map panel, north up."""
        info = self.map_info
        res, w, h = info.resolution, info.width, info.height
        col = (east - info.origin.position.x) / res
        row = (north - info.origin.position.y) / res
        scale = self.map_px / float(w)
        # Rows run north; the image is drawn top-first, so flip.
        return (int(round(col * scale)),
                int(round((h - row) * scale)))

    def metres_to_px(self, metres: float) -> int:
        info = self.map_info
        return int(round(metres / info.resolution * (self.map_px / float(info.width))))

    # ------------------------------------------------------------------
    def render(self) -> None:
        if self.grid is None or self.map_info is None:
            return

        panel = self.draw_map()
        text = self.draw_panel(panel.shape[0])
        hud = np.hstack([panel, text])

        out = self.bridge.cv2_to_imgmsg(np.ascontiguousarray(hud), encoding='bgr8')
        out.header.stamp = self.get_clock().now().to_msg()
        out.header.frame_id = 'map'
        self.hud_pub.publish(out)

    # ------------------------------------------------------------------
    def draw_map(self) -> np.ndarray:
        img = self.palette[np.flipud(self.grid)]
        img = cv2.resize(img, (self.map_px, self.map_px),
                         interpolation=cv2.INTER_NEAREST)

        # Metre grid, every 10 m, so distances on the HUD are readable without
        # measuring against the panel numbers.
        step = self.metres_to_px(10.0)
        if step > 8:
            for p in range(step, self.map_px, step):
                cv2.line(img, (p, 0), (p, self.map_px), (70, 70, 70), 1)
                cv2.line(img, (0, p), (self.map_px, p), (70, 70, 70), 1)

        vehicle = None
        if self.pos_enu is not None:
            vehicle = self.world_to_px(self.pos_enu[0], self.pos_enu[1])

        cand = self.candidate
        if cand is not None and cand.valid:
            c = self.world_to_px(cand.position.x, cand.position.y)
            # r_ideal: the circle the detector was trying to fit. Dashed, drawn
            # as short arcs, because it is an aspiration rather than a fact.
            r_ideal_px = self.metres_to_px(self.r_ideal)
            for a in range(0, 360, 20):
                cv2.ellipse(img, c, (r_ideal_px, r_ideal_px), 0, a, a + 10,
                            (150, 150, 150), 1)
            # Achieved clearance: the largest circle that actually fits here.
            cv2.circle(img, c, max(2, self.metres_to_px(cand.radius)),
                       (120, 255, 120), 2)
            # SORA separation the site holds against people and vehicles.
            cv2.circle(img, c, max(2, self.metres_to_px(self.r_hazard)),
                       (255, 170, 80), 1)
            cv2.drawMarker(img, c, (120, 255, 120), cv2.MARKER_CROSS, 16, 2)
            if vehicle is not None:
                cv2.line(img, vehicle, c, (120, 255, 120), 1, cv2.LINE_AA)

        if vehicle is not None:
            cv2.circle(img, vehicle, 6, (255, 255, 255), 2)
            cv2.line(img, (vehicle[0] - 11, vehicle[1]),
                     (vehicle[0] + 11, vehicle[1]), (255, 255, 255), 1)
            cv2.line(img, (vehicle[0], vehicle[1] - 11),
                     (vehicle[0], vehicle[1] + 11), (255, 255, 255), 1)

        cv2.putText(img, 'N', (self.map_px // 2 - 6, 18), FONT, 0.5,
                    (255, 255, 255), 1, cv2.LINE_AA)
        cv2.rectangle(img, (0, 0), (self.map_px - 1, self.map_px - 1),
                      (90, 90, 90), 1)
        return img

    # ------------------------------------------------------------------
    def draw_panel(self, height: int) -> np.ndarray:
        img = np.full((height, self.panel_px, 3), 24, dtype=np.uint8)
        y = [26]

        def line(text, color=(220, 220, 220), scale=0.42, gap=17):
            cv2.putText(img, text, (12, y[0]), FONT, scale, color, 1, cv2.LINE_AA)
            y[0] += gap

        def header(text):
            y[0] += 6
            cv2.putText(img, text, (12, y[0]), FONT, 0.40, (130, 190, 240), 1,
                        cv2.LINE_AA)
            y[0] += 4
            cv2.line(img, (12, y[0]), (self.panel_px - 12, y[0]), (60, 60, 60), 1)
            y[0] += 15

        st = self.state
        state_id = st.state if st is not None else None
        name = STATE_NAMES.get(state_id, 'MODE INACTIVE')
        color = STATE_COLORS.get(state_id, (140, 140, 140))
        cv2.putText(img, name, (12, y[0]), FONT, 0.68, color, 2, cv2.LINE_AA)
        y[0] += 24
        if st is not None:
            for chunk in self.wrap(st.reason, 40)[:3]:
                line(chunk, (160, 160, 160), 0.36, 14)
        else:
            line('mode not selected; PX4 is not', (160, 160, 160), 0.36, 14)
            line('calling updateSetpoint()', (160, 160, 160), 0.36, 14)

        header('VEHICLE')
        if self.pos_enu is not None:
            ground = math.hypot(self.vel_enu[0], self.vel_enu[1])
            line(f'altitude      {self.altitude:6.2f} m')
            line(f'ground speed  {ground:6.2f} m/s')
            line(f'vertical      {self.vel_enu[2]:+6.2f} m/s')
            line(f'position E/N  {self.pos_enu[0]:+.1f} / {self.pos_enu[1]:+.1f} m')
        else:
            line('no local position', (140, 140, 140))

        header('DESCENT LAW  (P, not PID)')
        if st is not None:
            law = 'area ratio' if st.area_law_active else 'altitude fallback'
            line(f'active input  {law}', (200, 220, 160))
            line(f'area_ratio    {st.area_ratio * 100:5.1f} %')
            line(f'ceiling       {st.descent_ceiling_mps:6.2f} m/s')
            line(f'commanded     {st.commanded_descent_mps:6.2f} m/s',
                 (140, 235, 140))
        else:
            line('idle', (140, 140, 140))
        line(f'k_size        {self.k_size:6.2f}', (170, 170, 170))
        line(f'v_min / v_max {self.v_min:.2f} / {self.v_max:.2f}', (170, 170, 170))
        line('Ki, Kd        not used', (140, 140, 140))

        header('CHOSEN SITE')
        cand = self.candidate
        if cand is not None and cand.valid:
            line(f'clearance     {cand.radius:6.2f} m  '
                 f'(want {self.r_ideal:.0f})', (140, 235, 140))
            line(f'area          {cand.area_m2:6.1f} m2')
            line(f'risk          {cand.risk_score:6.2f}')
            line(f'fills view    {cand.area_ratio * 100:5.1f} %')
            line(f'view bounded  {"yes" if cand.view_bounded else "no"}')
            if self.pos_enu is not None:
                d = math.hypot(cand.position.x - self.pos_enu[0],
                               cand.position.y - self.pos_enu[1])
                line(f'distance      {d:6.2f} m')
        else:
            line('no valid candidate', (120, 140, 240))

        header('LEGEND')
        line('solid green   clearance achieved', (120, 255, 120), 0.36, 14)
        line('dashed grey   r_ideal target', (150, 150, 150), 0.36, 14)
        # cv2 is BGR: this tuple is a light blue, not the orange it would be
        # if read as RGB. Getting that backwards is how the legend ended up
        # promising blue and drawing orange.
        line('thin blue     SORA separation', (255, 170, 80), 0.36, 14)
        return img

    @staticmethod
    def wrap(text: str, width: int):
        words, lines, cur = text.split(), [], ''
        for word in words:
            if len(cur) + len(word) + 1 > width:
                lines.append(cur)
                cur = word
            else:
                cur = f'{cur} {word}'.strip()
        if cur:
            lines.append(cur)
        return lines


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HudNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
