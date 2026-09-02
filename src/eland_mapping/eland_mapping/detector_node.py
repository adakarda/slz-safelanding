#!/usr/bin/env python3
"""Pick the best safe landing zone out of the semantic ground map.

**This is where landing policy lives.** ``safe_classes``, ``hazard_classes``
and ``class_risk`` are the only place a semantic class becomes "landable" --
no other node in the pipeline gets an opinion about it.

TWO SEPARATION RADII, NOT ONE
-----------------------------

An earlier version used a single ``r_safe`` distance-transform threshold for
everything, and that number was quietly doing two unrelated jobs:

  1. SORA separation from people and vehicles. This is an **absolute**
     requirement -- "3 m from a person unless the grass patch is small" is not
     a rule anyone would accept.
  2. "Does the aircraft physically fit here." This is about landing gear span
     plus margin, and for an x500 (~0.5 m across) it is nowhere near 3 m.

Collapsing them made a 4 m x 4 m patch of grass unselectable no matter how
empty its surroundings were: its best attainable clearance is 2 m, so a 3 m
threshold rejected it outright. Splitting them fixes that without weakening
the part that matters:

  ``r_hazard``  distance to the nearest cell of a ``hazard_classes`` type.
                Absolute, non-negotiable, this is the SORA rule.
  ``r_fit``     distance to the nearest cell that is not landable at all,
                hazard or otherwise. Small; this is geometry, not policy.

Region size is then a third, independent criterion, handled by connected
component analysis rather than by abusing a radius for it.
"""

import math

import cv2
import numpy as np
import rclpy
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from eland_common import classes
from eland_common.qos import DECISION_QOS, SENSOR_QOS
from eland_msgs.msg import LandingCandidate


class DetectorNode(Node):
    """Semantic ground grid -> single best LandingCandidate."""

    def __init__(self) -> None:
        super().__init__('detector_node')

        self.declare_parameter('safe_classes', classes.DEFAULT_SAFE_CLASSES)
        self.declare_parameter('hazard_classes', classes.DEFAULT_HAZARD_CLASSES)
        self.declare_parameter('r_hazard', 3.0)
        self.declare_parameter('r_fit', 1.0)
        self.declare_parameter('min_area_m2', 9.0)
        self.declare_parameter('r_ideal', 8.0)
        self.declare_parameter('w_risk', 0.50)
        self.declare_parameter('w_distance', 0.15)
        self.declare_parameter('w_clearance', 0.35)
        self.declare_parameter('max_rate_hz', 2.0)
        self.declare_parameter('map_topic', '/eland/ground_map')
        self.declare_parameter('mask_topic', '/eland/semantic_mask')
        self.declare_parameter('candidate_topic', '/eland/candidate')

        # class_risk arrives as a nested map, which ROS 2 flattens to
        # `class_risk.<id>`; declare one entry per known class ID.
        self.declare_parameters(
            namespace='',
            parameters=[
                (f'class_risk.{cid}', float(risk))
                for cid, risk in sorted(classes.DEFAULT_CLASS_RISK.items())
            ],
        )

        self.safe_classes = [int(c) for c in self.get_parameter('safe_classes').value]
        self.hazard_classes = [int(c) for c in self.get_parameter('hazard_classes').value]
        self.r_hazard = float(self.get_parameter('r_hazard').value)
        self.r_fit = float(self.get_parameter('r_fit').value)
        self.min_area_m2 = float(self.get_parameter('min_area_m2').value)
        self.r_ideal = float(self.get_parameter('r_ideal').value)
        self.w_risk = float(self.get_parameter('w_risk').value)
        self.w_distance = float(self.get_parameter('w_distance').value)
        self.w_clearance = float(self.get_parameter('w_clearance').value)
        max_rate = float(self.get_parameter('max_rate_hz').value)
        self.min_period_s = 1.0 / max_rate if max_rate > 0.0 else 0.0

        self.class_risk = np.array(
            [float(self.get_parameter(f'class_risk.{cid}').value)
             for cid in range(classes.NUM_CLASSES)],
            dtype=np.float32,
        )

        self.bridge = CvBridge()
        self.last_pub_time = None
        self.candidate_id = 0
        self.area_ratio = 0.0
        self.view_bounded = False
        self.have_mask = False

        self.candidate_pub = self.create_publisher(
            LandingCandidate,
            self.get_parameter('candidate_topic').value, DECISION_QOS)
        self.create_subscription(
            OccupancyGrid, self.get_parameter('map_topic').value,
            self.on_map, SENSOR_QOS)
        # The raw mask is subscribed *in addition to* the fused map, purely to
        # compute area_ratio in image space. Deriving that ratio from the
        # metric map instead would need the camera footprint, i.e. the
        # altitude -- and altitude independence is the whole reason the descent
        # law uses this quantity.
        self.create_subscription(
            Image, self.get_parameter('mask_topic').value,
            self.on_mask, SENSOR_QOS)

        safe_names = [classes.CLASS_NAMES.get(c, '?') for c in self.safe_classes]
        hazard_names = [classes.CLASS_NAMES.get(c, '?') for c in self.hazard_classes]
        self.get_logger().info(
            f'detector_node up: C_safe={self.safe_classes} {safe_names}, '
            f'hazards={self.hazard_classes} {hazard_names}, '
            f'r_hazard={self.r_hazard} m, r_fit={self.r_fit} m, '
            f'min_area={self.min_area_m2} m2, r_ideal={self.r_ideal} m, '
            f'w_risk={self.w_risk}, w_distance={self.w_distance}, '
            f'w_clearance={self.w_clearance}, max {max_rate:.1f} Hz')

    # ------------------------------------------------------------------
    def throttled(self) -> bool:
        now = self.get_clock().now()
        if self.last_pub_time is None:
            return False
        return (now - self.last_pub_time).nanoseconds * 1e-9 < self.min_period_s

    # ------------------------------------------------------------------
    def on_mask(self, msg: Image) -> None:
        """Compute the area ratio the descent law uses, in image space.

        The probe is the connected safe region under the image centre, i.e.
        directly beneath the aircraft. During VALIDATE and COMMIT that is the
        candidate the vehicle is descending onto, which is exactly when the
        ratio is used; during SEARCH and APPROACH nothing descends, so the
        value is not load-bearing there.
        """
        mask = self.bridge.imgmsg_to_cv2(msg)
        if mask.ndim == 3:
            mask = mask[:, :, 0]
        mask = mask.astype(np.uint8)

        safe = np.isin(mask, self.safe_classes).astype(np.uint8)
        total_px = safe.size
        if total_px == 0:
            return

        n_labels, labels = cv2.connectedComponents(safe, connectivity=8)
        cy, cx = mask.shape[0] // 2, mask.shape[1] // 2
        centre_label = int(labels[cy, cx])
        if centre_label == 0:
            # Nothing landable under the aircraft. Report zero rather than
            # falling back to the largest region somewhere else on screen: a
            # ratio that refers to ground we are not above would tell the
            # descent law to slow for a site it is not approaching.
            self.area_ratio = 0.0
            self.view_bounded = False
        else:
            region = labels == centre_label
            self.area_ratio = float(np.count_nonzero(region)) / total_px
            # Does the region run off the edge of the frame? If it does, its
            # ratio is only a lower bound on its true extent and carries no
            # information about how close we are -- see LandingCandidate.msg.
            self.view_bounded = not (
                region[0, :].any() or region[-1, :].any()
                or region[:, 0].any() or region[:, -1].any())
        self.have_mask = True

    # ------------------------------------------------------------------
    def on_map(self, msg: OccupancyGrid) -> None:
        if self.throttled():
            return
        self.last_pub_time = self.get_clock().now()

        w, h = msg.info.width, msg.info.height
        res = msg.info.resolution
        if w == 0 or h == 0 or res <= 0.0:
            self.get_logger().warning('degenerate ground_map, ignoring')
            return

        # data holds class IDs, not 0..100 occupancy. int8 wraps nothing here
        # because IDs are 0..9, but clamp anyway so a bad producer can't index
        # out of the risk table.
        grid = np.asarray(msg.data, dtype=np.int16).reshape(h, w)
        grid = np.clip(grid, 0, classes.NUM_CLASSES - 1).astype(np.uint8)

        # 1. binary safe mask
        safe = np.isin(grid, self.safe_classes).astype(np.uint8)
        if not safe.any():
            self.publish_invalid(msg, 'no cells in C_safe')
            return

        # 2. two independent clearances (see the module docstring)
        cell_area = res * res
        # DIST_MASK_PRECISE rather than the 5x5 chamfer approximation. The
        # chamfer mask under-reports Euclidean distance by a couple of percent,
        # which is invisible for a "does it fit" test and not something worth
        # accepting on a SORA separation. The exact transform costs more than
        # the chamfer one and nothing at this grid size.
        #
        # (It was switched while chasing a suspected 2.91 m separation against
        # a 3.0 m radius. That turned out to be a measurement error on my part
        # -- the shore was not where I assumed -- and the separation measures
        # 3.004 m either way. The change stands on its own merits, not on that
        # diagnosis.)
        dist_fit_m = cv2.distanceTransform(safe, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res

        hazard = np.isin(grid, self.hazard_classes).astype(np.uint8)
        if hazard.any():
            # distanceTransform measures distance to the nearest ZERO pixel, so
            # invert: non-hazard cells are the "free" space to measure through.
            dist_hazard_m = cv2.distanceTransform(
                1 - hazard, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res
        else:
            # No hazard in view at all -- the SORA separation is satisfied
            # everywhere, so do not let a missing constraint reject anything.
            dist_hazard_m = np.full(grid.shape, np.inf, dtype=np.float32)

        # 3. connected component analysis: region identity and metric area
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            safe, connectivity=8)
        # stats[:, CC_STAT_AREA] is in pixels; label 0 is the background.
        areas_m2 = stats[:, cv2.CC_STAT_AREA].astype(np.float32) * cell_area
        big_enough = areas_m2 >= self.min_area_m2
        big_enough[0] = False  # background is never a landing site

        # 4. eligibility: all three criteria, each answering its own question
        eligible = (big_enough[labels]
                    & (dist_fit_m >= self.r_fit)
                    & (dist_hazard_m >= self.r_hazard))
        if not eligible.any():
            self.publish_invalid(
                msg,
                f'nothing eligible (best fit {dist_fit_m.max():.2f}/{self.r_fit} m, '
                f'best hazard sep {np.max(dist_hazard_m[safe > 0]) if safe.any() else 0:.2f}'
                f'/{self.r_hazard} m, largest region '
                f'{areas_m2[1:].max() if len(areas_m2) > 1 else 0:.1f}/'
                f'{self.min_area_m2} m2)')
            return

        # 5. score. Three terms, all normalised to 0..1 and minimised:
        #
        #      w_risk      * risk        how bad is this surface
        #      w_distance  * norm_dist   how far must we fly to reach it
        #      w_clearance * shortfall   how far short of r_ideal is the
        #                                largest circle that fits here
        #
        #    The clearance term is what stops the vehicle landing on the verge.
        #    Without it, risk is 0 across every grass cell and the objective
        #    collapses to "nearest eligible cell" -- which is, by construction,
        #    a cell sitting exactly on the boundary of the exclusion zone, i.e.
        #    right against the kerb. Clearance was already being computed for
        #    the r_fit test; using it only as a threshold threw away the part
        #    that distinguishes the middle of a field from its edge.
        #
        #    r_ideal is the radius we would like to fit. Beyond it extra room
        #    earns nothing, so the vehicle stops trekking across the map in
        #    search of the geometric centre of the largest meadow.
        #
        #    mapping_node centres the map on the vehicle, so the drone sits at
        #    origin + half the map extent.
        drone_x = msg.info.origin.position.x + (w * res) / 2.0
        drone_y = msg.info.origin.position.y + (h * res) / 2.0

        ys, xs = np.nonzero(eligible)
        cell_x = msg.info.origin.position.x + (xs + 0.5) * res
        cell_y = msg.info.origin.position.y + (ys + 0.5) * res

        d_from_drone = np.hypot(cell_x - drone_x, cell_y - drone_y)
        max_d = math.hypot(w * res, h * res) / 2.0
        norm_d = d_from_drone / max_d if max_d > 0.0 else np.zeros_like(d_from_drone)

        risk = self.class_risk[grid[ys, xs]]
        clearance = dist_fit_m[ys, xs]
        shortfall = np.clip(1.0 - clearance / max(self.r_ideal, 1e-6), 0.0, 1.0)
        score = (self.w_risk * risk
                 + self.w_distance * norm_d
                 + self.w_clearance * shortfall)

        # 6. argmin
        best = int(np.argmin(score))
        best_label = int(labels[ys[best], xs[best]])
        self.publish_candidate(
            msg,
            x=float(cell_x[best]),
            y=float(cell_y[best]),
            radius=float(dist_fit_m[ys[best], xs[best]]),
            risk=float(risk[best]),
            area_m2=float(areas_m2[best_label]),
            n_eligible=int(eligible.sum()),
            score=float(score[best]),
        )

    # ------------------------------------------------------------------
    def publish_candidate(self, map_msg, x, y, radius, risk, area_m2,
                          n_eligible, score) -> None:
        out = LandingCandidate()
        out.header.stamp = map_msg.header.stamp
        out.header.frame_id = map_msg.header.frame_id or 'map'
        out.position.x = x
        out.position.y = y
        out.position.z = 0.0
        out.radius = radius
        out.risk_score = risk
        out.area_m2 = area_m2
        out.area_ratio = float(self.area_ratio)
        out.view_bounded = bool(self.view_bounded)
        # STUB: real confidence comes from the segmentation model's per-pixel
        # posterior fused over time. Stand-in: how much of the map cleared the
        # eligibility test, capped at 1.0.
        total = map_msg.info.width * map_msg.info.height
        out.confidence = float(min(1.0, (n_eligible / total) * 10.0)) if total else 0.0
        out.candidate_id = self.candidate_id % 256
        out.valid = True
        self.candidate_pub.publish(out)
        self.candidate_id += 1

        self.get_logger().debug(
            f'candidate #{out.candidate_id} ({x:.2f}, {y:.2f}) r={radius:.2f} m '
            f'area={area_m2:.1f} m2 ratio={out.area_ratio:.3f} risk={risk:.2f} '
            f'V={score:.3f} eligible={n_eligible}')

    def publish_invalid(self, map_msg, reason: str) -> None:
        out = LandingCandidate()
        out.header.stamp = map_msg.header.stamp
        out.header.frame_id = map_msg.header.frame_id or 'map'
        out.radius = 0.0
        out.risk_score = 1.0
        out.confidence = 0.0
        out.area_ratio = 0.0
        out.area_m2 = 0.0
        out.view_bounded = False
        out.candidate_id = self.candidate_id % 256
        out.valid = False
        self.candidate_pub.publish(out)
        self.candidate_id += 1
        self.get_logger().debug(f'no candidate: {reason}')


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DetectorNode()
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
