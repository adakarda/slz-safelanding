#!/usr/bin/env python3
"""Track the moving obstacles and say where they are going.

WHAT IT READS, AND WHY NOT THE OTHER MAP

`/eland/ground_map_instant`, not `/eland/ground_map`. The fused map cannot
represent a fast mover at all: evidence per cell settles at about rate * tau,
roughly 90 at 3 Hz with a 30 s memory, and a vehicle crossing a cell in 1.5 s
deposits about 5. It loses the argmax every time. Measured on this machine
with a labelled vehicle driving through the origin at 3 m/s: Gazebo's own
segmentation showed two vehicle blobs, one moving, while /eland/ground_map
showed only the parked one, centroid steady to within 0.2 m over twelve
samples 3 s apart.

That memory is not a defect to be tuned away -- without it the aircraft cannot
land at all -- so the fix is to look at the frame before it is fused, which is
what mapping_node now publishes alongside it. Same projection, same geometry,
no second IPM implementation to drift.

WHY CONSTANT VELOCITY AND NOTHING CLEVERER

A Kalman filter would model process noise honestly, and it would be modelling
noise this pipeline does not measure. What arrives is a blob centroid at ~3 Hz
whose position error is dominated by two things a filter cannot see: the class
mask flickering at the object's edge, and the flat-ground assumption in the
IPM putting a 1.8 m tall person about 0.3 m off. Over a 4 s horizon a straight
line through the last few centroids is inside that error, and its failure mode
-- a turning obstacle -- is not fixed by a filter that also assumes constant
velocity. What does help is admitting how bad the estimate is, so `confidence`
falls with the residual of the fit and the corridor built downstream widens.

WHAT IT DOES NOT DO

No occlusion reasoning, no re-identification across a lost track, no
interacting-multiple-model anything. A track that vanishes for longer than
`track_timeout_s` is forgotten, and if the same object comes back it comes
back as a new id with no velocity until it has been seen a few times more.
That is deliberately conservative: a fresh track has low confidence, which
downstream widens the exclusion rather than narrowing it.
"""
from __future__ import annotations

import math

import cv2
from eland_common import classes
from eland_common.qos import DECISION_QOS, SENSOR_QOS
from eland_msgs.msg import DynamicObstacle, DynamicObstacleArray
from geometry_msgs.msg import Point, Vector3
from nav_msgs.msg import OccupancyGrid
import numpy as np
import rclpy
from rclpy.node import Node


class Track:
    """One obstacle's history and the line fitted through it."""

    __slots__ = ('id', 'class_id', 'times', 'xs', 'ys', 'last_seen', 'born')

    def __init__(self, track_id, class_id, t, x, y):
        self.id = track_id
        self.class_id = class_id
        self.times = [t]
        self.xs = [x]
        self.ys = [y]
        self.born = t
        self.last_seen = t

    def add(self, t, x, y, history_len):
        self.times.append(t)
        self.xs.append(x)
        self.ys.append(y)
        self.last_seen = t
        if len(self.times) > history_len:
            del self.times[0]
            del self.xs[0]
            del self.ys[0]

    @property
    def position(self):
        return self.xs[-1], self.ys[-1]

    def fit(self):
        """Least-squares velocity, plus the residual that fit left behind.

        Returns (vx, vy, rms_residual_m). Two observations give a velocity
        with a zero residual, which is honest arithmetic and dishonest
        confidence -- the caller weights by observation count as well.
        """
        n = len(self.times)
        if n < 2:
            return 0.0, 0.0, 0.0
        t = np.asarray(self.times)
        t = t - t[0]
        if t[-1] <= 0.0:
            return 0.0, 0.0, 0.0
        A = np.vstack([t, np.ones_like(t)]).T
        (vx, x0), *_ = np.linalg.lstsq(A, np.asarray(self.xs), rcond=None)
        (vy, y0), *_ = np.linalg.lstsq(A, np.asarray(self.ys), rcond=None)
        rx = np.asarray(self.xs) - (vx * t + x0)
        ry = np.asarray(self.ys) - (vy * t + y0)
        rms = float(np.sqrt(np.mean(rx ** 2 + ry ** 2)))
        return float(vx), float(vy), rms


class TrackerNode(Node):

    def __init__(self) -> None:
        super().__init__('tracker_node')

        self.declare_parameter('instant_map_topic', '/eland/ground_map_instant')
        self.declare_parameter('obstacles_topic', '/eland/dynamic_obstacles')
        # Which classes are allowed to move. Buildings and water are not on
        # this list, so a flickering building edge never becomes a 20 m/s
        # obstacle that clears the map.
        self.declare_parameter('dynamic_classes', [8, 9])
        # Blobs smaller than this are noise at the mask's edge. A person is
        # about 0.28 m^2 seen from above, which is 7 cells at 0.2 m -- so this
        # cannot be raised much without going blind to people.
        self.declare_parameter('min_blob_cells', 5)
        self.declare_parameter('max_blob_cells', 4000)
        # A blob touching the edge of the map is a blob whose other half is
        # outside it, so its centroid is the centroid of the visible part and
        # it creeps inward as the object leaves. Fitting a velocity through
        # that reads as an obstacle slowing down exactly when it is about to
        # matter. Measured with the vehicle turning around at the map edge:
        # mean fitted speed 2.09 m/s against a true 3.0.
        #
        # Same reasoning as the detector's view_bounded flag: a measurement
        # bounded by the frame rather than by the object is not a measurement
        # of the object.
        self.declare_parameter('ignore_border_blobs', True)
        self.declare_parameter('border_margin_cells', 1)
        # Nearest-neighbour gate. At 3 m/s and 3 Hz an obstacle moves 1 m per
        # frame; 4 m leaves room for centroid jitter without letting two
        # obstacles swap identities across a 20 m map.
        self.declare_parameter('association_radius_m', 4.0)
        self.declare_parameter('history_len', 8)
        # A track outlives its last observation, and that is the point. An
        # obstacle that drives off the edge of a 40 m map has not stopped
        # existing; it is still on the road it was on. Measured consequence of
        # forgetting it immediately: the aircraft committed to a site while
        # the vehicle was briefly outside the map, and the vehicle then drove
        # over the touchdown point.
        #
        # The coasting track's confidence decays to zero across this window,
        # so the corridor it projects widens as the evidence for it ages
        # instead of standing at full strength until it vanishes.
        self.declare_parameter('track_timeout_s', 6.0)
        self.declare_parameter('min_observations_for_velocity', 3)
        self.declare_parameter('max_speed_mps', 15.0)
        self.declare_parameter('horizon_s', 4.0)
        self.declare_parameter('prediction_steps', 4)

        gp = self.get_parameter
        self.dynamic_classes = [int(c) for c in gp('dynamic_classes').value]
        self.min_blob = int(gp('min_blob_cells').value)
        self.max_blob = int(gp('max_blob_cells').value)
        self.ignore_border = bool(gp('ignore_border_blobs').value)
        self.border_margin = int(gp('border_margin_cells').value)
        self.assoc_r = float(gp('association_radius_m').value)
        self.history_len = int(gp('history_len').value)
        self.timeout_s = float(gp('track_timeout_s').value)
        self.min_obs = int(gp('min_observations_for_velocity').value)
        self.max_speed = float(gp('max_speed_mps').value)
        self.horizon_s = float(gp('horizon_s').value)
        self.steps = max(1, int(gp('prediction_steps').value))

        self.tracks: list[Track] = []
        self.next_id = 1

        self.pub = self.create_publisher(
            DynamicObstacleArray, gp('obstacles_topic').value, DECISION_QOS)
        self.create_subscription(
            OccupancyGrid, gp('instant_map_topic').value, self.on_map, SENSOR_QOS)

        self.get_logger().info(
            f'tracking classes {self.dynamic_classes} on '
            f'{gp("instant_map_topic").value}, {self.horizon_s:.1f} s horizon')

    # ------------------------------------------------------------------
    def on_map(self, msg: OccupancyGrid) -> None:
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        grid = np.array(msg.data, dtype=np.int16).reshape(
            msg.info.height, msg.info.width)
        res = msg.info.resolution
        ox = msg.info.origin.position.x
        oy = msg.info.origin.position.y

        detections = self.detect(grid, res, ox, oy)
        self.associate(detections, t)
        self.expire(t)
        self.publish(msg.header.stamp, t)

    def detect(self, grid, res, ox, oy):
        """Connected components of each dynamic class, as metric centroids."""
        out = []
        for cid in self.dynamic_classes:
            mask = (grid == cid).astype(np.uint8)
            if not mask.any():
                continue
            n, _, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
            h, w = grid.shape
            for i in range(1, n):
                area = int(stats[i, cv2.CC_STAT_AREA])
                if area < self.min_blob or area > self.max_blob:
                    continue
                if self.ignore_border:
                    x0 = stats[i, cv2.CC_STAT_LEFT]
                    y0 = stats[i, cv2.CC_STAT_TOP]
                    x1 = x0 + stats[i, cv2.CC_STAT_WIDTH]
                    y1 = y0 + stats[i, cv2.CC_STAT_HEIGHT]
                    m = self.border_margin
                    if x0 <= m or y0 <= m or x1 >= w - m or y1 >= h - m:
                        continue
                # Grid col/row -> ENU metres. The +0.5 puts the point at the
                # cell centre; without it every position carries a systematic
                # half-cell (0.1 m) bias toward the origin.
                cx = ox + (cents[i][0] + 0.5) * res
                cy = oy + (cents[i][1] + 0.5) * res
                out.append((cid, cx, cy, area))
        return out

    def associate(self, detections, t):
        """Greedy nearest neighbour, same class only.

        Greedy rather than Hungarian: with two obstacles on a 40 m map the
        assignment is never ambiguous, and an optimal matcher would be code
        whose failure mode nobody here has ever seen.
        """
        unmatched = list(detections)
        for track in self.tracks:
            best, best_d = None, self.assoc_r
            tx, ty = track.position
            for det in unmatched:
                if det[0] != track.class_id:
                    continue
                d = math.hypot(det[1] - tx, det[2] - ty)
                if d < best_d:
                    best, best_d = det, d
            if best is not None:
                track.add(t, best[1], best[2], self.history_len)
                unmatched.remove(best)

        for cid, cx, cy, _area in unmatched:
            self.tracks.append(Track(self.next_id, cid, t, cx, cy))
            self.next_id += 1

    def expire(self, t):
        alive = [tr for tr in self.tracks if t - tr.last_seen <= self.timeout_s]
        for tr in self.tracks:
            if tr not in alive:
                self.get_logger().debug(
                    f'track {tr.id} ({classes.CLASS_NAMES[tr.class_id]}) lost')
        self.tracks = alive

    # ------------------------------------------------------------------
    def publish(self, stamp, t):
        msg = DynamicObstacleArray()
        msg.header.stamp = stamp
        msg.header.frame_id = 'map'
        msg.horizon_s = self.horizon_s

        for track in self.tracks:
            vx, vy, rms = track.fit()
            n = len(track.times)
            if n < self.min_obs:
                # Seen, not yet understood. Published with zero velocity so
                # downstream still applies the static separation to it.
                vx = vy = 0.0
                conf = 0.0
            else:
                speed = math.hypot(vx, vy)
                if speed > self.max_speed:
                    # Almost always identity confusion between two blobs of
                    # the same class rather than a genuinely fast obstacle.
                    self.get_logger().warning(
                        f'track {track.id} fitted {speed:.1f} m/s, above '
                        f'{self.max_speed:.1f}; velocity discarded')
                    vx = vy = 0.0
                    conf = 0.0
                else:
                    count_term = min(1.0, (n - 1) / max(1, self.history_len - 1))
                    # 0.5 m of residual halves the confidence: that is about
                    # one person-width of centroid wander, past which the fit
                    # is describing mask flicker rather than motion.
                    fit_term = 1.0 / (1.0 + (rms / 0.5) ** 2)
                    # And how stale the last look at it is. A coasting track
                    # is a memory, not an observation.
                    stale = (t - track.last_seen) / max(self.timeout_s, 1e-6)
                    age_term = max(0.0, 1.0 - stale)
                    conf = float(count_term * fit_term * age_term)

            ob = DynamicObstacle()
            ob.id = track.id
            ob.class_id = track.class_id
            ob.position = Point(x=track.position[0], y=track.position[1], z=0.0)
            ob.velocity = Vector3(x=vx, y=vy, z=0.0)
            ob.speed = float(math.hypot(vx, vy))
            ob.confidence = conf
            ob.age_s = float(t - track.born)
            ob.observations = len(track.times)

            for k in range(1, self.steps + 1):
                dt = self.horizon_s * k / self.steps
                ob.predicted.append(Point(
                    x=track.position[0] + vx * dt,
                    y=track.position[1] + vy * dt,
                    z=0.0))
                ob.predicted_times.append(float(dt))

            msg.obstacles.append(ob)

        self.pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TrackerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
