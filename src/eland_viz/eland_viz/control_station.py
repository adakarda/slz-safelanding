#!/usr/bin/env python3
"""Control station: the HUD plus a keyboard, in one window.

    ros2 run eland_viz control_station

Exists because every landing test used to start from wherever the vehicle was
spawned, and the site the detector picks is usually the patch of grass
immediately beneath it. Being able to fly somewhere first -- over the road,
next to the person, onto the paved yard -- turns one scenario per launch into
as many as you care to fly.

WHY MANUAL CONTROL AND NOT OFFBOARD

The vehicle is flown by publishing ManualControlSetpoint on
/fmu/in/manual_control_input, which PX4 treats exactly like a joystick: it
flies in Position mode, holding altitude and position when the sticks are
centred, and the sticks are body-relative so forward means where the nose is
pointing. Verified in SITL before this file was written -- PX4 switched to
nav_state 2 and flew 14.8 m on a 0.6 pitch stick.

The alternative would have been offboard setpoints, which is precisely the
mechanism this whole project exists to avoid: it bypasses PX4's mode and
failsafe logic. A test tool has no business doing that when a supported input
path exists.

STICKS ARE STICKY

OpenCV reports key presses but not releases, so a key sets a stick value that
stays set until you centre it. In practice that suits testing better than a
held key would: point the vehicle, watch it fly, press SPACE.

IT ALSO HOLDS THE GCS LINK OPEN, AND HAS TO

PX4 tracks whether a ground station is talking to it, and NAV_DLL_ACT defaults
to Return. With no GCS attached at all, `gcs_connection_lost` goes true
COM_DL_LOSS_T (10 s) after takeoff and that failsafe fires -- and since the
Emergency Landing mode is registered in place of Return, the vehicle lands
itself roughly fifteen seconds into every flight, whatever you were trying to
do with it. That is not a bug in this station; it is the failsafe working, and
it made the first three teleop attempts here look like broken controls.

So the station sends a GCS heartbeat, because that is what a ground station
is. The link exists while the window is open and drops when it closes -- at
which point the failsafe brings up the landing mode, which is the intended
demonstration rather than an accident.

ONE MORE CONSEQUENCE

Once manual control is streaming, PX4 also has a manual control link, and
COM_RC_LOSS_T is 0.5 s. That is why the stream runs on its own timer under a
background executor and not from the render loop: a stall in cv2.imshow must
not be able to look like a lost transmitter.
"""

import math
import threading
import time

import cv2
import numpy as np
import rclpy
import rclpy.executors
from px4_msgs.msg import (ManualControlSetpoint, VehicleCommand,
                          VehicleLocalPosition, VehicleStatus)
from rclpy.node import Node
from sensor_msgs.msg import Image
from eland_common import px4_topics
from eland_common.qos import PX4_QOS, SENSOR_QOS

FONT = cv2.FONT_HERSHEY_SIMPLEX

CMD_SET_NAV_STATE = 100001
NAV_POSCTL = 2
NAV_LAND = 18
NAV_EXTERNAL1 = 23

#: How far one key press deflects a stick. Small enough that a single tap is a
#: nudge rather than a lurch; press twice to go faster.
STICK_STEP = 0.3
STICK_MAX = 1.0

#: Seconds of neutral sticks to stream before asking PX4 for Position mode.
#: Two was enough in every test; one was not always.
MANUAL_SETTLE_S = 2.0

KEY_HELP = [
    ('W / S', 'ileri / geri'),
    ('A / D', 'sola / saga kay'),
    ('Q / E', 'sola / saga don'),
    ('R / F', 'yuksel / alcal'),
    ('SPACE', 'cubuklari ortala'),
    ('', ''),
    ('1', 'arm'),
    ('2', 'kalkis'),
    ('3', 'manuel kontrolu al (POSCTL)'),
    ('0', 'ACIL INIS modunu tetikle'),
    ('L', "PX4 ile in"),
    ('X', 'disarm'),
    ('ESC', 'cik'),
]


class ControlStation(Node):
    def __init__(self) -> None:
        super().__init__('control_station')

        self.declare_parameter('hud_topic', '/eland/hud')
        self.declare_parameter('manual_rate_hz', 20.0)
        # 14550 is where PX4 sends; 18570 is where its "Normal" mavlink
        # instance listens. Heartbeats aimed at 14550 are never seen by the
        # autopilot, so the link it is meant to notice would never exist.
        self.declare_parameter('gcs_heartbeat', True)
        self.declare_parameter('px4_mavlink_endpoint', 'udpout:127.0.0.1:18570')
        self.declare_parameter(
            'vehicle_local_position_topic', px4_topics.VEHICLE_LOCAL_POSITION)
        self.declare_parameter('vehicle_status_topic', '/fmu/out/vehicle_status_v4')

        self.hud = None
        self.pos = None
        self.status = None
        self.manual_active = False
        self.posctl_request_at = None
        self.sticks = {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0, 'throttle': 0.0}
        self.notice = 'baslatildi -- 1: arm, 2: kalkis, 3: manuel kontrol'

        self.manual_pub = self.create_publisher(
            ManualControlSetpoint, '/fmu/in/manual_control_input', PX4_QOS)
        self.cmd_pub = self.create_publisher(
            VehicleCommand, '/fmu/in/vehicle_command', PX4_QOS)
        self.create_subscription(
            Image, self.get_parameter('hud_topic').value, self.on_hud, SENSOR_QOS)
        self.create_subscription(
            VehicleLocalPosition,
            self.get_parameter('vehicle_local_position_topic').value,
            self.on_pos, PX4_QOS)
        self.create_subscription(
            VehicleStatus, self.get_parameter('vehicle_status_topic').value,
            self.on_status, PX4_QOS)

        # The manual control stream runs on its own timer, spun by a background
        # executor, deliberately not from the render loop. PX4 treats a gap
        # longer than COM_RC_LOSS_T (0.5 s by default) as a lost transmitter,
        # and with the Emergency Landing mode registered in place of Return
        # that failsafe takes the aircraft. A momentary stall in cv2.imshow is
        # not something the flight link should depend on.
        period = 1.0 / float(self.get_parameter('manual_rate_hz').value)
        self.create_timer(period, self.publish_manual)
        self.create_timer(0.1, self.service_pending_mode)

        self.gcs = None
        if bool(self.get_parameter('gcs_heartbeat').value):
            self.start_gcs_heartbeat()
        self.get_logger().info('control_station up -- pencereye tikla, klavye orada calisir')

    # ------------------------------------------------------------------
    def start_gcs_heartbeat(self) -> None:
        """Announce ourselves as a ground station, once per second.

        Over MAVLink rather than DDS because "is a GCS connected" is a MAVLink
        notion: PX4 counts heartbeats arriving at its mavlink instance, and no
        uORB topic substitutes for that.
        """
        try:
            from pymavlink import mavutil
        except ImportError:
            self.get_logger().warning(
                'pymavlink yok -- GCS heartbeat gonderilemiyor. PX4 '
                'COM_DL_LOSS_T (10 s) sonra baglanti kaybi failsafe ine girer '
                've arac kendi kendine iner. Kur: pip install pymavlink')
            return

        endpoint = self.get_parameter('px4_mavlink_endpoint').value
        try:
            self.gcs = mavutil.mavlink_connection(
                endpoint, source_system=255, source_component=190)
        except Exception as exc:  # noqa: BLE001 - never take the station down
            self.get_logger().warning(f'GCS heartbeat acilamadi ({exc})')
            return

        def beat():
            while rclpy.ok():
                try:
                    self.gcs.mav.heartbeat_send(
                        mavutil.mavlink.MAV_TYPE_GCS,
                        mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0,
                        mavutil.mavlink.MAV_STATE_ACTIVE)
                except Exception:  # noqa: BLE001
                    return
                time.sleep(1.0)

        threading.Thread(target=beat, daemon=True).start()
        self.get_logger().info(f'GCS heartbeat -> {endpoint}')

    # ------------------------------------------------------------------
    def on_hud(self, msg: Image) -> None:
        self.hud = np.frombuffer(msg.data, np.uint8).reshape(
            msg.height, msg.width, 3).copy()

    def on_pos(self, msg: VehicleLocalPosition) -> None:
        self.pos = msg

    def on_status(self, msg: VehicleStatus) -> None:
        self.status = msg

    # ------------------------------------------------------------------
    def now(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9

    def stamp(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)

    def service_pending_mode(self) -> None:
        """Send the deferred Position mode request once the stream is live."""
        if self.posctl_request_at is None or self.now() < self.posctl_request_at:
            return
        self.posctl_request_at = None
        self.set_nav_state(NAV_POSCTL)
        self.notice = 'manuel kontrol alindi (POSCTL) -- WASD/QE/RF ile ucur'

    def publish_manual(self) -> None:
        """Stream the sticks. Must keep going once started, or PX4 sees a lost
        manual control link within COM_RC_LOSS_T."""
        if not self.manual_active:
            return
        m = ManualControlSetpoint()
        m.timestamp = m.timestamp_sample = self.stamp()
        m.valid = True
        m.data_source = ManualControlSetpoint.SOURCE_MAVLINK_0
        m.roll = float(self.sticks['roll'])
        m.pitch = float(self.sticks['pitch'])
        m.yaw = float(self.sticks['yaw'])
        m.throttle = float(self.sticks['throttle'])
        m.sticks_moving = any(abs(v) > 0.01 for v in self.sticks.values())
        self.manual_pub.publish(m)

    def send_command(self, command: int, p1=0.0, p2=0.0) -> None:
        c = VehicleCommand()
        c.timestamp = self.stamp()
        c.command = command
        c.param1 = float(p1)
        c.param2 = float(p2)
        c.target_system = c.target_component = 1
        c.source_system = 255
        c.source_component = 190
        c.from_external = True
        self.cmd_pub.publish(c)

    def set_nav_state(self, nav_state: int) -> None:
        self.send_command(CMD_SET_NAV_STATE, nav_state)

    # ------------------------------------------------------------------
    def nudge(self, axis: str, delta: float) -> None:
        self.sticks[axis] = float(
            np.clip(self.sticks[axis] + delta, -STICK_MAX, STICK_MAX))

    def handle_key(self, key: int) -> bool:
        """Returns False to quit."""
        k = chr(key).lower() if 32 <= key < 127 else ''
        if key == 27:  # ESC
            return False
        elif k == 'w':
            self.nudge('pitch', STICK_STEP)
        elif k == 's':
            self.nudge('pitch', -STICK_STEP)
        elif k == 'd':
            self.nudge('roll', STICK_STEP)
        elif k == 'a':
            self.nudge('roll', -STICK_STEP)
        elif k == 'e':
            self.nudge('yaw', STICK_STEP)
        elif k == 'q':
            self.nudge('yaw', -STICK_STEP)
        elif k == 'r':
            self.nudge('throttle', STICK_STEP)
        elif k == 'f':
            self.nudge('throttle', -STICK_STEP)
        elif key == 32:  # space
            for a in self.sticks:
                self.sticks[a] = 0.0
            self.notice = 'cubuklar ortalandi'
        elif k == '1':
            # -f: without a GCS attached the preflight check refuses on "no
            # connection to the GCS", which is not a real problem in SITL.
            self.send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                              1.0, 21196.0)
            self.notice = 'arm istendi'
        elif k == 'x':
            self.send_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM,
                              0.0, 21196.0)
            self.notice = 'disarm istendi'
        elif k == '2':
            self.send_command(VehicleCommand.VEHICLE_CMD_NAV_TAKEOFF)
            self.notice = 'kalkis istendi'
        elif k == '3':
            # Start the stream now, ask for the mode a moment later. PX4 will
            # not hand over to a manual control source it has not yet seen, and
            # requesting POSCTL in the same breath as enabling the publisher
            # means exactly zero messages have gone out when the request
            # arrives. Measured: doing both at once left the vehicle in AUTO
            # with sticks deflected, and the failsafe took it 7 s later.
            for a in self.sticks:
                self.sticks[a] = 0.0
            self.manual_active = True
            self.posctl_request_at = self.now() + MANUAL_SETTLE_S
            self.notice = 'manuel kontrol kuruluyor...'
        elif k == 'l':
            self.set_nav_state(NAV_LAND)
            self.notice = "PX4 iniş modu"
        elif k == '0':
            self.set_nav_state(NAV_EXTERNAL1)
            self.notice = 'ACIL INIS modu tetiklendi'
        return True

    # ------------------------------------------------------------------
    def render(self) -> np.ndarray:
        if self.hud is not None:
            hud = self.hud
        else:
            hud = np.full((520, 850, 3), 24, np.uint8)
            cv2.putText(hud, 'HUD bekleniyor (/eland/hud)', (30, 260), FONT,
                        0.7, (120, 120, 120), 1, cv2.LINE_AA)

        strip = np.full((250, hud.shape[1], 3), 18, np.uint8)
        cv2.line(strip, (0, 0), (strip.shape[1], 0), (70, 70, 70), 1)

        # Key help, two columns.
        for i, (key, what) in enumerate(KEY_HELP):
            col, row = divmod(i, 7)
            x = 14 + col * 250
            y = 26 + row * 20
            if key:
                cv2.putText(strip, key, (x, y), FONT, 0.44, (120, 200, 255), 1,
                            cv2.LINE_AA)
                cv2.putText(strip, what, (x + 62, y), FONT, 0.40, (200, 200, 200),
                            1, cv2.LINE_AA)

        # Stick state, as bars, so a stick left deflected is obvious.
        bx = 14 + 2 * 250
        cv2.putText(strip, 'CUBUKLAR', (bx, 26), FONT, 0.42, (130, 190, 240), 1,
                    cv2.LINE_AA)
        for i, axis in enumerate(('pitch', 'roll', 'yaw', 'throttle')):
            y = 48 + i * 22
            v = self.sticks[axis]
            cv2.putText(strip, f'{axis:9s}{v:+.1f}', (bx, y + 4), FONT, 0.40,
                        (200, 200, 200), 1, cv2.LINE_AA)
            x0 = bx + 110
            cv2.line(strip, (x0, y), (x0 + 120, y), (60, 60, 60), 3)
            mid = x0 + 60
            cv2.line(strip, (mid, y - 5), (mid, y + 5), (90, 90, 90), 1)
            end = int(mid + v * 58)
            if abs(v) > 0.01:
                cv2.line(strip, (mid, y), (end, y), (120, 235, 120), 3)

        # Vehicle state.
        sx = bx + 250
        cv2.putText(strip, 'DURUM', (sx, 26), FONT, 0.42, (130, 190, 240), 1,
                    cv2.LINE_AA)
        armed = ''
        nav = ''
        if self.status is not None:
            armed = ('ARMED' if self.status.arming_state == 2 else 'disarmed')
            nav = f'nav_state {self.status.nav_state}'
        manual = 'manuel: AKTIF' if self.manual_active else 'manuel: kapali'
        rows = [armed, nav, manual]
        if self.pos is not None:
            rows.append(f'alt {-self.pos.z:.1f} m')
            rows.append(f'hiz {math.hypot(self.pos.vx, self.pos.vy):.1f} m/s')
        for i, text in enumerate(rows):
            color = (120, 235, 120) if text == 'ARMED' else (200, 200, 200)
            cv2.putText(strip, text, (sx, 48 + i * 20), FONT, 0.40, color, 1,
                        cv2.LINE_AA)

        cv2.putText(strip, self.notice, (14, strip.shape[0] - 14), FONT, 0.42,
                    (240, 200, 120), 1, cv2.LINE_AA)
        return np.vstack([hud, strip])


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ControlStation()

    # Spin in the background so the timers keep firing while the main thread is
    # busy drawing. Rendering must never be able to interrupt the flight link.
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    spinner = threading.Thread(target=executor.spin, daemon=True)
    spinner.start()

    window = 'eland control station'
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    try:
        while rclpy.ok():
            cv2.imshow(window, node.render())
            key = cv2.waitKey(30)
            if key != -1 and not node.handle_key(key & 0xFF):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
