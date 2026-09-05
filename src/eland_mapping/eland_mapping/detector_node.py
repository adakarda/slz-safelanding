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
import time

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
        # Distance to the nearest cell of a DIFFERENT class, whatever that
        # class is. r_fit cannot see the seam between two landable classes,
        # because both are in safe_classes and the distance transform runs on
        # their union: a site on the kerb between grass and pavement reports
        # the clearance of the whole open area around it.
        #
        # That seam is worth a criterion of its own for two reasons that have
        # nothing to do with SORA. It is where the mask is least reliable --
        # every class boundary flickers by a cell or two per frame, and the
        # flat-ground IPM misplaces a raised kerb by more than that. And in
        # this world it is usually a real step: grass to road is a kerb, not a
        # painted line, and a leg on a kerb is a tip-over.
        self.declare_parameter('r_class_edge', 0.0)
        self.declare_parameter('min_area_m2', 9.0)
        self.declare_parameter('r_ideal', 8.0)
        self.declare_parameter('w_risk', 0.50)
        self.declare_parameter('w_distance', 0.15)
        self.declare_parameter('w_clearance', 0.35)
        # What a site costs for being ground something crossed within the
        # memory, scaled by how recently. Same order as w_clearance on
        # purpose: freshly crossed ground should lose to any comparable site
        # and win against nothing at all.
        self.declare_parameter('w_memory', 0.35)
        # What a site costs for sitting in the shadow of a corridor as seen
        # from the aircraft. Lower than w_memory because the aircraft crosses
        # that ground at altitude and only briefly, where a landing site is
        # occupied for the whole descent.
        self.declare_parameter('w_route', 0.20)
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
        # Keep the site already chosen while it is still allowed, instead of
        # re-running the argmin every frame and possibly landing somewhere
        # else because a cell two metres away scored a thousandth better.
        #
        # The eligibility tests are unchanged and still run first, so a site
        # the corridor now covers is gone from the candidates before this is
        # consulted: the latch can prolong a decision, never override a
        # rejection. What it removes is the churn -- and the churn was not
        # cosmetic, because the flight mode reads a candidate that jumped as a
        # candidate it lost, and three of those end the attempt budget.
        #
        # The margin is the escape hatch: if something genuinely better shows
        # up, better by this much on the 0..1 score, the latch releases.
        self.declare_parameter('latch_site', True)
        self.declare_parameter('latch_release_margin', 0.20)
        # How far the held site may be re-found before it counts as the same
        # site. Requiring the identical cell (the old behaviour, res * 1.5)
        # made the latch an all-or-nothing thing: one frame in which that one
        # cell was not eligible -- a flickering mask edge, a mover's disc
        # grazing it -- dropped the latch entirely and the next candidate
        # arrived a clearing away. Measured on the pinned three-people,
        # two-vehicle landing: candidates jumping more than 4 m, and the mode
        # logging "candidate lost at 11-14 m" while already hovering over the
        # site. A landing site is a disc metres across, so the nearest still
        # eligible cell within this radius is the same site, not a new one.
        self.declare_parameter('latch_radius_m', 2.0)
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
        # The exclusion this filter actually applied, as a grid, for the HUD.
        #
        # Published rather than recomputed on the display side for the same
        # reason the descent speed is: a HUD that derives the corridor from
        # the same parameters can drift away from the detector without either
        # of them being obviously wrong, and the picture would then be
        # reassuring instead of true. 100 = the predicted corridor, 50 =
        # ground something moved across, 0 = clear.
        self.declare_parameter('block_map_topic', '/eland/trajectory_block')
        self.declare_parameter('publish_block_map', True)

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
        self.r_class_edge = float(self.get_parameter('r_class_edge').value)
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

        self.w_memory = float(self.get_parameter('w_memory').value)
        self.w_route = float(self.get_parameter('w_route').value)
        self.w_sticky = float(self.get_parameter('w_stickiness').value)
        self.sticky_radius = float(self.get_parameter('stickiness_radius_m').value)
        self.latch_site = bool(self.get_parameter('latch_site').value)
        self.latch_margin = float(self.get_parameter('latch_release_margin').value)
        self.latch_radius = float(self.get_parameter('latch_radius_m').value)

        self.corridor_memory_s = float(
            self.get_parameter('corridor_memory_s').value)
        self.publish_block_map = bool(
            self.get_parameter('publish_block_map').value)

        self.obstacles = None
        self.obstacles_time = None
        self.rejected_by_trajectory = 0
        self.last_choice = None
        self.swept = []          # (x, y, r, t) ground something moved over

        self.bridge = CvBridge()
        self.stage_times = {}
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
        self.create_timer(10.0, self.report_stages)
        self.block_pub = self.create_publisher(
            OccupancyGrid, self.get_parameter('block_map_topic').value,
            SENSOR_QOS)

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
    def stage(self, name, t0):
        now = time.perf_counter()
        self.stage_times.setdefault(name, []).append(now - t0)
        return now

    def report_stages(self):
        """Where a decision frame goes, p50 and p95, every ten seconds.

        The trajectory test rasterises a corridor per moving obstacle and the
        approach test walks every candidate cell against every disc, so this
        is the part that grows with traffic. Whether it is actually the
        expensive part is a question with an answer, and this is it.
        """
        if not self.stage_times:
            return
        parts = []
        for name, samples in self.stage_times.items():
            if not samples:
                continue
            ordered = sorted(samples)
            p50 = ordered[len(ordered) // 2] * 1000.0
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] * 1000.0
            parts.append(f'{name} {p50:.1f}/{p95:.1f}')
        self.stage_times = {}
        self.get_logger().info('decision ms (p50/p95): ' + '  '.join(parts))

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
        """Ground something moved across recently, as (x, y, r, recency).

        `recency` runs from 1 at the instant of the crossing to 0 at the end
        of the memory, and it is a weight, not a veto. Two measured reasons.

        It cannot be part of the approach-path test: a route is a bad place to
        sit down and a perfectly good place to fly over at fifteen metres, and
        including remembered ground there once blocked 95% of the map.

        It cannot be a hard site exclusion either. With five movers the
        remembered discs covered every one of ~20 000 otherwise eligible cells
        on 79 of 152 frames, so the detector published nothing and the mode
        abandoned the descent three times -- into PX4's blind Descend, which
        is worse than any of the ground it was refusing. Ranking that ground
        last says the same thing without ever emptying the set: a spot a car
        crossed 2 s ago costs a full `w_memory`, one crossed 28 s ago costs
        almost nothing, and both stay landable if the alternative is nowhere.
        """
        if not self.traj_enabled or self.corridor_memory_s <= 0.0:
            return []
        now = self.get_clock().now().nanoseconds * 1e-9
        out = []
        for (x, y, r, t) in self.swept:
            age = now - t
            if age <= self.corridor_memory_s:
                out.append((x, y, r, 1.0 - age / self.corridor_memory_s))
        return out

    def corridor_radius(self, t, confidence):
        """r_hazard, widened by how wrong the prediction is likely to be
        across the path -- along it, the union of discs already covers the
        error. Scaled by (2 - confidence), so a track the tracker does not
        believe in gets twice the margin of one it does. Confidence is clamped
        because a malformed message must widen the corridor, never narrow it.
        """
        conf = min(max(float(confidence), 0.0), 1.0)
        return self.r_hazard + (self.sigma_base + self.sigma_rate * t) * (2.0 - conf)

    def rasterise_block(self, info, drone, discs, memory):
        """Draw the exclusion instead of computing it per cell.

        The arithmetic version tested every candidate cell against every disc,
        twice -- once for the site and once for the route -- and it dominated
        the decision frame: profiled at 44 ms of a 48 ms frame, against 0.9 ms
        for the distance transform and 0.2 ms for the connected components.
        With traffic there are a hundred-odd discs and twenty thousand
        candidate cells, so that is a couple of million element operations per
        frame to answer a question about geometry.

        Drawn instead: each disc is a filled circle, and each route shadow is
        the quadrilateral between the two tangent lines from the aircraft,
        starting at the tangency points so the ground between the aircraft and
        the obstacle is not excluded for no reason. Both are single OpenCV
        fills over a 200x200 image.

        Returns (site_blocked, route_shadow, memory_cost). Only the first is
        an exclusion -- ground a hazard is predicted to occupy, which is the
        one thing the aircraft must not sit on. The other two are costs the
        score pays.

        The shadow is a cost because as an exclusion it was measured to leave
        nothing at all: with traffic it covered every one of ~21 000 otherwise
        eligible cells on every frame, while the corridor alone left 4 000 to
        12 000. That is the difference between "prefer not to fly over a
        hazard on the way down" -- true, and worth a weight -- and "never fly
        over one", which at five movers means never land.
        """
        h, w, res = info.height, info.width, info.resolution
        ox, oy = info.origin.position.x, info.origin.position.y
        site = np.zeros((h, w), dtype=np.uint8)
        route = np.zeros((h, w), dtype=np.uint8)
        mem_cost = np.zeros((h, w), dtype=np.float32)

        def to_px(x, y):
            return (int(round((x - ox) / res)), int(round((y - oy) / res)))

        def circle(img, cx, cy, r, value=1):
            cv2.circle(img, to_px(cx, cy), max(1, int(round(r / res))),
                       value, -1)

        for cx, cy, r in discs:
            circle(site, cx, cy, r)
        # Stalest first, so where two crossings overlap the fresher one sets
        # the cost.
        for cx, cy, r, recency in sorted(memory, key=lambda d: d[3]):
            circle(mem_cost, cx, cy, r, float(recency))

        if self.check_approach and drone is not None:
            reach = math.hypot(w * res, h * res)
            for cx, cy, r in discs:
                dx, dy = cx - drone[0], cy - drone[1]
                dist = math.hypot(dx, dy)
                if dist <= r:
                    # Horizontally inside this disc. The old code set the whole
                    # map here, reasoning that every direction out of the
                    # corridor crosses it -- but the aircraft is fifteen metres
                    # above the disc, not in it, and the corridor is a
                    # ground-plane construct. Blanking the map on a person
                    # walking under the aircraft is the stuck-vehicle failure
                    # this file warns about elsewhere. No shadow from this
                    # disc; the disc itself is still excluded as a site.
                    continue
                # Tangent points from the aircraft to the circle, and the wedge
                # they open beyond it.
                ang = math.atan2(dy, dx)
                half = math.asin(min(1.0, r / dist))
                tangent_len = math.sqrt(max(0.0, dist * dist - r * r))
                pts = []
                for sign in (1.0, -1.0):
                    a = ang + sign * half
                    near = (drone[0] + math.cos(a) * tangent_len,
                            drone[1] + math.sin(a) * tangent_len)
                    far = (drone[0] + math.cos(a) * (tangent_len + reach),
                           drone[1] + math.sin(a) * (tangent_len + reach))
                    pts.append((near, far))
                poly = np.array([to_px(*pts[0][0]), to_px(*pts[0][1]),
                                 to_px(*pts[1][1]), to_px(*pts[1][0])],
                                dtype=np.int32)
                cv2.fillPoly(route, [poly], 1)

        return site, route, mem_cost

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

        t0 = time.perf_counter()
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
        t0 = self.stage('safe-mask', t0)
        dist_fit_m = cv2.distanceTransform(safe, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res

        # Distance to the nearest class boundary. The boundary itself is any
        # cell with a 4-neighbour of a different class, so the edge of the
        # camera footprint counts too -- ground the aircraft cannot see the
        # far side of is not ground it should aim at the middle of.
        edge = np.zeros(grid.shape, dtype=np.uint8)
        edge[:, :-1] |= (grid[:, :-1] != grid[:, 1:]).astype(np.uint8)
        edge[:, 1:] |= (grid[:, 1:] != grid[:, :-1]).astype(np.uint8)
        edge[:-1, :] |= (grid[:-1, :] != grid[1:, :]).astype(np.uint8)
        edge[1:, :] |= (grid[1:, :] != grid[:-1, :]).astype(np.uint8)
        dist_edge_m = cv2.distanceTransform(
            1 - edge, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res

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

        t0 = self.stage('distance', t0)
        # 3. connected component analysis: region identity and metric area
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
            safe, connectivity=8)
        # stats[:, CC_STAT_AREA] is in pixels; label 0 is the background.
        areas_m2 = stats[:, cv2.CC_STAT_AREA].astype(np.float32) * cell_area
        big_enough = areas_m2 >= self.min_area_m2
        big_enough[0] = False  # background is never a landing site

        t0 = self.stage('components', t0)
        # 4. eligibility: all three criteria, each answering its own question
        eligible = (big_enough[labels]
                    & (dist_fit_m >= self.r_fit)
                    & (dist_edge_m >= self.r_class_edge)
                    & (dist_hazard_m >= self.r_hazard))
        if not eligible.any():
            self.publish_invalid(
                msg,
                f'nothing eligible (best fit {dist_fit_m.max():.2f}/{self.r_fit} m, '
                f'best class-edge sep {dist_edge_m.max():.2f}/'
                f'{self.r_class_edge} m, '
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
        t0 = self.stage('eligibility', t0)
        discs = self.corridor_discs()
        memory = self.memory_discs()
        n_before = len(cell_x)
        mem_cost_cells = None
        route_cost_cells = None
        if discs or memory:
            site_blocked, route_blocked, mem_cost = self.rasterise_block(
                msg.info, (drone_x, drone_y), discs, memory)
            if self.publish_block_map:
                self.publish_block(msg, site_blocked, route_blocked, mem_cost)
            keep = site_blocked[ys, xs] == 0
            if not keep.any():
                # Only the corridor can empty the set now, and when it does
                # that is a real answer: everywhere the aircraft could sit is
                # somewhere a hazard is about to be. HOLD/ABORT is right --
                # SafeLand's reactive behaviour, kept as the fallback it was
                # always meant to be.
                self.publish_invalid(
                    msg,
                    f'{n_before} cells passed the static tests, all of them '
                    f'inside the predicted path ({len(discs)} corridor '
                    f'samples)')
                return
            ys, xs = ys[keep], xs[keep]
            cell_x, cell_y = cell_x[keep], cell_y[keep]
            self.rejected_by_trajectory = n_before - int(keep.sum())
            mem_cost_cells = mem_cost[ys, xs]
            route_cost_cells = route_blocked[ys, xs].astype(np.float32)
        else:
            self.rejected_by_trajectory = 0

        t0 = self.stage('trajectory', t0)
        d_from_drone = np.hypot(cell_x - drone_x, cell_y - drone_y)
        max_d = math.hypot(w * res, h * res) / 2.0
        norm_d = d_from_drone / max_d if max_d > 0.0 else np.zeros_like(d_from_drone)

        risk = self.class_risk[grid[ys, xs]]
        # The ranking uses whichever clearance is worse. A site three metres
        # from a kerb is not as open as one three metres from a kerb and
        # thirty from anything else, and only this term can tell them apart.
        clearance = np.minimum(dist_fit_m[ys, xs], dist_edge_m[ys, xs])
        shortfall = np.clip(1.0 - clearance / max(self.r_ideal, 1e-6), 0.0, 1.0)
        score = (self.w_risk * risk
                 + self.w_distance * norm_d
                 + self.w_clearance * shortfall)
        # Remembered ground is priced, never forbidden (see memory_discs).
        if mem_cost_cells is not None and self.w_memory > 0.0:
            score = score + self.w_memory * mem_cost_cells
        # So is a site whose approach passes over a predicted corridor.
        if route_cost_cells is not None and self.w_route > 0.0:
            score = score + self.w_route * route_cost_cells

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

        # 6. argmin, unless the site already chosen is still on the table
        best = int(np.argmin(score))
        if self.latch_site and self.last_choice is not None:
            d_prev = np.hypot(cell_x - self.last_choice[0],
                              cell_y - self.last_choice[1])
            held = int(np.argmin(d_prev))
            # The same site, not necessarily the same cell (see latch_radius_m).
            if d_prev[held] <= max(self.latch_radius, res * 1.5):
                if score[held] - score[best] <= self.latch_margin:
                    best = held
                else:
                    self.get_logger().info(
                        f'latch released: a site scoring '
                        f'{score[best]:.3f} beat the held one at '
                        f'{score[held]:.3f} by more than {self.latch_margin}')
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
            edge_m=float(dist_edge_m[ys[best], xs[best]]),
        )
        self.stage('score+publish', t0)

    # ------------------------------------------------------------------
    def publish_block(self, map_msg, site, route, mem_cost) -> None:
        """The exclusion this frame used, for display only.

        The same masks the decision was made from, not a second rendering of
        the same idea: a HUD that draws its own version of the corridor can
        drift away from the detector while both look plausible.

        100 = the predicted corridor, the only hard exclusion left. 70 = the
        approach shadow and 20..60 = ground something moved across, shaded by
        how recently: both are costs the score pays, not places it may not go,
        so they deliberately do not look like the corridor.
        """
        info = map_msg.info
        img = np.where(route > 0, np.uint8(70), np.uint8(0))
        img = np.where(site > 0, np.uint8(100), img)
        if mem_cost is not None:
            shade = (20.0 + 40.0 * np.clip(mem_cost, 0.0, 1.0)).astype(np.uint8)
            img = np.where((mem_cost > 0.0) & (img == 0), shade, img)

        out = OccupancyGrid()
        out.header = map_msg.header
        out.info = info
        out.data = img.astype(np.int8).ravel().tolist()
        self.block_pub.publish(out)

    def publish_candidate(self, map_msg, x, y, radius, risk, area_m2,
                          n_eligible, score, edge_m=float('nan')) -> None:
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
        # Info, throttled: the one number request 1 is about. "Clearance
        # 7.40 m" said nothing about how far the site sat from the seam
        # between two landable classes, because nothing measured it.
        self.get_logger().info(
            f'secilen site: sinif sinirina {edge_m:.2f} m, '
            f'inilebilir alanin kenarina {radius:.2f} m',
            throttle_duration_sec=5.0)
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
        # Info, throttled, not debug: the mode abandons a descent after 3 s
        # without a valid candidate, and on a measured landing 3 of the 6 empty
        # stretches crossed that threshold -- the longest ran 10 s from 9.9 m.
        # A node that is the direct cause of a state transition should say so
        # in the log the operator already reads.
        self.get_logger().info(f'aday yok: {reason}',
                               throttle_duration_sec=2.0)


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
