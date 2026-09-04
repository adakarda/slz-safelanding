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

A FOURTH TEST: WHERE THE HAZARD IS GOING
----------------------------------------

The three tests above all ask about the world as it is now. A vehicle doing
3 m/s covers 12 m in the four seconds a descent takes, so "3 m from a vehicle"
is satisfied by a spot the vehicle will be sitting on by the time the aircraft
arrives. ``trajectory_clear`` adds the missing question: is this site, and the
route to it, clear of where the moving hazards are going?

This is the layer that is ours rather than the literature's. SafeLand
(arXiv:2603.17430) handles dynamic obstacles reactively -- if one enters the
safety radius, pause 5 s, and if it is still there climb back to search
altitude and reroute. That is entirely based on the obstacle's present
position. The reactive half is kept, unchanged, in the flight mode's
HOLD/ABORT states; what is added here is a predictive filter that runs before
it, so a site is never chosen if the hazard is heading for it. Reactive
behaviour remains the fallback for everything prediction gets wrong -- an
obstacle that turns, accelerates, or was never tracked at all.

The corridor is deliberately wider than the prediction. Measured on this
machine, constant-velocity extrapolation of a tracked vehicle had a mean error
of about 2.4 m at one second and 5.0 m at four; a corridor of exactly
``r_hazard`` around a predicted point would therefore be a 3 m separation from
a position that is itself several metres wrong. So the corridor grows with the
horizon and with the tracker's own stated confidence -- see ``corridor_radius``.
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
from eland_msgs.msg import DynamicObstacleArray, LandingCandidate


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

        # --- the trajectory-aware test ---------------------------------
        # Off restores the purely reactive behaviour, which is what the
        # comparison run needs: the same scenario with and without this layer
        # is the only evidence that it changes anything.
        self.declare_parameter('trajectory_filter_enabled', True)
        self.declare_parameter('obstacles_topic', '/eland/dynamic_obstacles')
        # Older than this and the obstacle list is treated as absent rather
        # than as "nothing is moving". A silent tracker is not an empty world.
        self.declare_parameter('obstacle_timeout_s', 2.0)
        # Below this speed an obstacle is standing still as far as the horizon
        # is concerned, and the ordinary r_hazard separation already covers it.
        # 0.5 m/s is also about the noise floor of the tracker's velocity fit.
        self.declare_parameter('obstacle_min_speed_mps', 0.5)
        # Corridor width = r_hazard + (base + cross_rate * t) * (2 - confidence).
        #
        # base is the tracker's measured position error, ~1.5 m.
        #
        # cross_rate is small on purpose, and the reason is worth stating. The
        # measured prediction error grows about 0.9 m per second of horizon,
        # but nearly all of that is ALONG the predicted path -- it is the
        # obstacle being a little ahead of or behind where the constant-speed
        # line puts it. The corridor is the union of discs sampled along that
        # same line, so along-track error is already inside it; widening every
        # disc by it would double-count. What the disc radius has to cover is
        # error ACROSS the path, which comes from heading noise in the fit --
        # traced at roughly 0.2 m/s of spurious lateral velocity.
        self.declare_parameter('pred_sigma_base_m', 1.5)
        self.declare_parameter('pred_sigma_cross_rate_mps', 0.25)
        # Also refuse sites whose straight-line approach crosses the corridor.
        # Conservative on purpose: it ignores whether the aircraft would
        # actually be there at the same time. Space-time reasoning would need
        # a trajectory for the aircraft that does not exist yet at selection
        # time, and the cost of being early is a slightly longer flight.
        self.declare_parameter('check_approach_path', True)
        self.declare_parameter('corridor_samples', 8)
        # Stickiness: a small discount for staying with the site already
        # chosen, while it remains eligible.
        #
        # This is not cosmetic. A moving corridor makes the best site jump --
        # while the vehicle's predicted path covers the origin the winner is
        # 12 m away, and the moment the corridor moves off it the origin wins
        # again. The flight mode reads a candidate that jumped that far as a
        # candidate it lost, and three of those exhaust the retry budget and
        # end in "no retries left, committing anyway". Measured: three lost
        # candidates and a commit-anyway in a run where nothing was actually
        # wrong with the site it had.
        #
        # The discount is smaller than the difference between a good site and
        # a bad one, so it breaks ties and resists flapping without letting
        # the aircraft stay somewhere it should leave.
        self.declare_parameter('w_stickiness', 0.15)
        self.declare_parameter('stickiness_radius_m', 3.0)
        # How long a stretch of ground that something drove or walked over
        # stays excluded, seconds. 0 disables the memory.
        #
        # A forward-only corridor answers "where is it going" and nothing
        # else, and that turned out to be half the question. Measured: with a
        # vehicle crossing the landing area, the aircraft correctly refused
        # the site while the vehicle was inbound, waited, and then landed on
        # exactly that spot the moment the vehicle had passed and the corridor
        # moved off it -- touchdown 0.37 m from the line the vehicle drives
        # along, which it then drove along again.
        #
        # A moving obstacle is evidence about the ground, not only about
        # itself: something that just drove through here is a route, and a
        # route is a bad place to sit down. Each frame's observation is
        # remembered as a disc, so a crossing leaves its whole swept path
        # excluded, and the exclusion ages out rather than accumulating
        # forever.
        self.declare_parameter('corridor_memory_s', 25.0)

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

        self.traj_enabled = bool(
            self.get_parameter('trajectory_filter_enabled').value)
        self.obstacle_timeout_s = float(
            self.get_parameter('obstacle_timeout_s').value)
        self.obstacle_min_speed = float(
            self.get_parameter('obstacle_min_speed_mps').value)
        self.sigma_base = float(self.get_parameter('pred_sigma_base_m').value)
        self.sigma_rate = float(
            self.get_parameter('pred_sigma_cross_rate_mps').value)
        self.check_approach = bool(self.get_parameter('check_approach_path').value)
        self.corridor_samples = max(2, int(self.get_parameter('corridor_samples').value))

        self.w_sticky = float(self.get_parameter('w_stickiness').value)
        self.sticky_radius = float(self.get_parameter('stickiness_radius_m').value)

        self.corridor_memory_s = float(
            self.get_parameter('corridor_memory_s').value)

        self.obstacles = None
        self.obstacles_time = None
        self.rejected_by_trajectory = 0
        self.last_choice = None
        self.swept = []          # (x, y, r, t) ground something moved over

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
        self.create_subscription(
            DynamicObstacleArray, self.get_parameter('obstacles_topic').value,
            self.on_obstacles, DECISION_QOS)

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
    def on_obstacles(self, msg: DynamicObstacleArray) -> None:
        self.obstacles = msg
        self.obstacles_time = self.get_clock().now()
        if self.corridor_memory_s <= 0.0 or not self.traj_enabled:
            return
        now = self.obstacles_time.nanoseconds * 1e-9
        for ob in msg.obstacles:
            if ob.speed < self.obstacle_min_speed:
                continue
            # Only where it was actually seen. Remembering the predicted part
            # of the corridor as well would turn one extrapolation into a
            # permanent record of a place nothing has ever been.
            #
            # Thinned to one disc per metre of path: at 3 Hz an obstacle
            # deposits three overlapping discs a second, and every one of them
            # costs a full pass over the candidate cells later. The discs are
            # 4.5 m across, so a metre of spacing leaves no gap.
            if any(math.hypot(ob.position.x - sx, ob.position.y - sy) < 1.0
                   for sx, sy, _sr, _st in self.swept):
                continue
            self.swept.append((ob.position.x, ob.position.y,
                               self.r_hazard + self.sigma_base, now))
        cutoff = now - self.corridor_memory_s
        self.swept = [s for s in self.swept if s[3] >= cutoff]

    def corridor_discs(self):
        """Where the moving hazards will be, as (x, y, radius) discs.

        One disc per sampled instant per moving obstacle, from now to the
        tracker's horizon. Returns an empty list when the filter is off, when
        the obstacle list is stale, or when nothing is moving fast enough to
        matter -- and the caller distinguishes those cases in its logging,
        because "no obstacles" and "no tracker" have to look different.
        """
        if not self.traj_enabled or self.obstacles is None:
            return []
        age = (self.get_clock().now() - self.obstacles_time).nanoseconds * 1e-9
        if age > self.obstacle_timeout_s:
            return []

        horizon = float(self.obstacles.horizon_s) or 0.0
        discs = []
        for ob in self.obstacles.obstacles:
            if ob.speed < self.obstacle_min_speed:
                continue
            for k in range(self.corridor_samples + 1):
                t = horizon * k / self.corridor_samples
                x = ob.position.x + ob.velocity.x * t
                y = ob.position.y + ob.velocity.y * t
                discs.append((x, y, self.corridor_radius(t, ob.confidence)))
        return discs

    def memory_discs(self):
        """Ground something moved across recently. Site exclusion only.

        These are NOT part of the approach-path test, and the asymmetry is the
        point. A route is a bad place to sit down; it is not a bad place to
        fly over at fifteen metres. Including remembered ground in the route
        test blocked 95% of the map in a measured run -- every direction from
        the aircraft was shadowed by ground a car had crossed at some point in
        the last half minute -- which is not caution, it is a stuck vehicle.
        """
        if not self.traj_enabled or self.corridor_memory_s <= 0.0:
            return []
        now = self.get_clock().now().nanoseconds * 1e-9
        return [(x, y, r) for (x, y, r, t) in self.swept
                if now - t <= self.corridor_memory_s]

    def corridor_radius(self, t, confidence):
        """r_hazard, widened by how wrong the prediction is likely to be
        across the path -- along it, the union of discs already covers the
        error. Scaled by (2 - confidence), so a track the tracker does not
        believe in gets twice the margin of one it does. Confidence is clamped
        because a malformed message must widen the corridor, never narrow it.
        """
        conf = min(max(float(confidence), 0.0), 1.0)
        return self.r_hazard + (self.sigma_base + self.sigma_rate * t) * (2.0 - conf)

    @staticmethod
    def _segment_point_distance(px, py, ax, ay, bx, by):
        """Distance from each point (px, py) to the segment AB. Vectorised."""
        dx, dy = bx - ax, by - ay
        # Any of these may be arrays -- the caller passes a scalar disc centre
        # against an array of candidate cells -- so the degenerate case is
        # selected elementwise rather than branched on.
        denom = dx * dx + dy * dy
        safe_denom = np.where(denom > 1e-9, denom, 1.0)
        s = np.clip(((px - ax) * dx + (py - ay) * dy) / safe_denom, 0.0, 1.0)
        s = np.where(denom > 1e-9, s, 0.0)
        return np.hypot(px - (ax + s * dx), py - (ay + s * dy))

    def trajectory_clear(self, cell_x, cell_y, drone_x, drone_y, discs,
                         site_only_discs=()):
        """True where a cell is outside every corridor disc, and -- when
        check_approach_path is on -- where the straight line from the aircraft
        to that cell is too.

        The approach test is the same distance test read the other way round:
        the route is a segment, so a disc blocks it when the disc's centre is
        within its radius of that segment.
        """
        clear = np.ones(cell_x.shape, dtype=bool)
        for cx, cy, r in discs:
            clear &= np.hypot(cell_x - cx, cell_y - cy) >= r
            if self.check_approach:
                d = self._segment_point_distance(
                    cx, cy, drone_x, drone_y, cell_x, cell_y)
                clear &= d >= r
        for cx, cy, r in site_only_discs:
            clear &= np.hypot(cell_x - cx, cell_y - cy) >= r
        return clear

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

        # 4b. the fourth test. Applied to the cells that already passed the
        #     other three rather than to the whole grid: it is the expensive
        #     one, and a cell that is not landable now does not become
        #     interesting because nothing is driving towards it.
        discs = self.corridor_discs()
        memory = self.memory_discs()
        n_before = len(cell_x)
        if discs or memory:
            keep = self.trajectory_clear(cell_x, cell_y, drone_x, drone_y,
                                         discs, memory)
            if not keep.any():
                self.publish_invalid(
                    msg,
                    f'{n_before} cells passed the static tests, all of them '
                    f'inside the predicted path ({len(discs)} corridor '
                    f'samples) or on ground something moved across '
                    f'({len(memory)} remembered discs)')
                return
            ys, xs = ys[keep], xs[keep]
            cell_x, cell_y = cell_x[keep], cell_y[keep]
            self.rejected_by_trajectory = n_before - int(keep.sum())
        else:
            self.rejected_by_trajectory = 0

        d_from_drone = np.hypot(cell_x - drone_x, cell_y - drone_y)
        max_d = math.hypot(w * res, h * res) / 2.0
        norm_d = d_from_drone / max_d if max_d > 0.0 else np.zeros_like(d_from_drone)

        risk = self.class_risk[grid[ys, xs]]
        clearance = dist_fit_m[ys, xs]
        shortfall = np.clip(1.0 - clearance / max(self.r_ideal, 1e-6), 0.0, 1.0)
        score = (self.w_risk * risk
                 + self.w_distance * norm_d
                 + self.w_clearance * shortfall)

        # 5b. stay where we were, if where we were is still allowed. Applied
        #     after the eligibility tests, never instead of them: a site the
        #     corridor now covers has already been removed from these arrays,
        #     so stickiness can prolong a choice but cannot revive a rejected
        #     one.
        if self.last_choice is not None and self.w_sticky > 0.0:
            near_last = (np.hypot(cell_x - self.last_choice[0],
                                  cell_y - self.last_choice[1])
                         <= self.sticky_radius)
            score = score - self.w_sticky * near_last

        # 6. argmin
        best = int(np.argmin(score))
        self.last_choice = (float(cell_x[best]), float(cell_y[best]))
        best_label = int(labels[ys[best], xs[best]])
        self.publish_candidate(
            msg,
            x=float(cell_x[best]),
            y=float(cell_y[best]),
            radius=float(dist_fit_m[ys[best], xs[best]]),
            risk=float(risk[best]),
            area_m2=float(areas_m2[best_label]),
            n_eligible=len(cell_x),
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
            f'V={score:.3f} eligible={n_eligible} '
            f'trajectory-rejected={self.rejected_by_trajectory}')
        # Info level, and only when it actually changed something: a filter
        # that silently discards two thirds of the map should say so once per
        # crossing, not never and not every frame.
        if self.rejected_by_trajectory:
            self.get_logger().info(
                f'trajectory filter removed {self.rejected_by_trajectory} of '
                f'{self.rejected_by_trajectory + n_eligible} otherwise eligible '
                f'cells; landing at ({x:.2f}, {y:.2f})')

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
