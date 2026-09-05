#!/usr/bin/env python3
"""Project the semantic mask into a metric ground map under the drone.

Publishes ``nav_msgs/OccupancyGrid`` on ``/eland/ground_map``.

WHY THIS NODE HAS A MEMORY
--------------------------

The obvious implementation -- overwrite the grid with the current camera
footprint every frame -- cannot land the aircraft, and the failure is not
subtle. The footprint width is ``2 * altitude * tan(hfov/2)``: about 36 m at
the 15 m search altitude, but only 7 m at 3 m. Everything outside it is
UNKNOWN, which ``detector_node`` correctly treats as un-landable, so a
memoryless map runs out of usable ground exactly when the aircraft is
committed to descending.

Measured before this was fixed: the vehicle cycled
VALIDATE -> HOLD -> ABORT -> climb -> SEARCH -> VALIDATE four times in 90 s,
losing the candidate at 2.77 m, 2.86 m, 3.09 m and 3.15 m. It never landed.

The memory matters for safety too, not just continuity. A hazard that leaves
the camera's view is forgotten by a memoryless map: the person's own cells go
UNKNOWN, so nothing lands *on* them, but the 3 m SORA buffer around them
disappears, because ``r_hazard`` cannot enforce a separation from a hazard it
can no longer see.

HOW THE PROJECTION WORKS
------------------------

Each mask pixel is a ray. Its direction in the camera frame is ``K^-1 p``;
rotating that into NED and intersecting with the ground plane gives the metric
point it came from. Because the ground is a plane, the whole mapping collapses
into a single 3x3 homography from image pixels to map cells, which is what
``groundHomography()`` builds and ``cv2.warpPerspective`` applies.

This replaced a nadir approximation that pasted a scaled copy of the mask into
the middle of the grid. That approximation had two errors beyond the obvious
one of ignoring roll and pitch:

  * It ignored heading entirely, so the map only made sense pointing north.
  * It pasted image row 0 into grid row 0. OccupancyGrid row 0 is the *origin*
    row, i.e. the southernmost, while image row 0 is the top of the frame,
    i.e. the vehicle's forward direction. The map was mirrored north-south.

Neither showed up in earlier tests because the chosen landing site was always
almost directly beneath the aircraft, where a mirrored map and a correct one
agree.

GRID SEMANTICS: ``OccupancyGrid.data`` holds *semantic class IDs* (0..9, see
eland_common.classes), NOT the standard ROS occupancy range of 0..100 with -1
for unknown. RViz's map display renders this as near-black nonsense -- that is
expected. The only consumer is ``detector_node``, which reads them as IDs.
"""

import math
import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from nav_msgs.msg import OccupancyGrid
from px4_msgs.msg import VehicleAttitude, VehicleLocalPosition
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image
from eland_common import classes, px4_topics
from eland_common.qos import PX4_QOS, SENSOR_QOS

#: Optical frame -> body FRD, for the downward camera in x500_seg_cam_down.
#:
#: The model pitches the sensor +90 deg about Y, which in Gazebo's FLU frame
#: turns the optical axis (+X) into -Z, i.e. straight down. Carrying that
#: through to the OpenCV optical convention (z along the axis, x right in the
#: image, y down in the image) and converting FLU -> FRD gives:
#:
#:     image x (right) -> body +Y (right)
#:     image y (down)  -> body -X (backward)
#:     image z (axis)  -> body +Z (down)
#:
#: Columns of this matrix are those three axes expressed in body FRD.
R_BODY_CAM = np.array([
    [0.0, -1.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0],
], dtype=np.float64)


def quaternion_to_matrix(q) -> np.ndarray:
    """PX4 VehicleAttitude.q (w, x, y, z), body FRD -> NED."""
    w, x, y, z = float(q[0]), float(q[1]), float(q[2]), float(q[3])
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


class MappingNode(Node):
    """Semantic mask + vehicle pose -> fused metric semantic ground grid."""

    def __init__(self) -> None:
        super().__init__('mapping_node')

        self.declare_parameter('map_size_m', 40.0)
        self.declare_parameter('map_resolution', 0.2)
        self.declare_parameter('camera_hfov_deg', 90.0)
        # Evidence half-life. A cell observed once and then never seen again
        # stays above min_evidence for roughly 4.3 * tau seconds.
        self.declare_parameter('memory_tau_s', 30.0)
        self.declare_parameter('min_evidence', 0.05)
        # Past this tilt the projection stops being trustworthy: with a 99.7
        # deg horizontal FOV the frame starts to include the horizon at about
        # 40 deg, and rays near it project to enormous distances or behind the
        # camera. Dropping the frame is better than fusing a smear.
        self.declare_parameter('max_tilt_deg', 30.0)
        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('mask_topic', '/eland/semantic_mask')
        self.declare_parameter('map_topic', '/eland/ground_map')
        self.declare_parameter('debug_image_topic', '/eland/ground_map_colored')
        self.declare_parameter('publish_debug_image', True)
        # This frame's projection, before it is fused into the accumulator.
        #
        # The fused map cannot see anything that moves, and that is not a bug
        # to fix here: evidence accumulates to roughly rate * tau (about 90 at
        # 3 Hz with tau=30 s), so a vehicle crossing a cell in 1.5 s deposits
        # about 5 against the ground's 90 and loses the argmax every time.
        # Measured: with a labelled vehicle driving through the origin at
        # 3 m/s, gz's own segmentation showed two vehicle blobs while
        # /eland/ground_map showed only the parked one, its centroid steady to
        # 0.2 m across twelve samples.
        #
        # Shortening tau for dynamic classes would trade away the memory the
        # descent depends on, so instead the raw per-frame projection is
        # published alongside the fused map and whoever cares about motion --
        # tracker_node -- reads that. The IPM stays in one place.
        self.declare_parameter('instant_map_topic', '/eland/ground_map_instant')
        self.declare_parameter('publish_instant_map', True)
        self.declare_parameter('camera_info_topic', '/camera/camera_info')
        self.declare_parameter(
            'vehicle_local_position_topic', px4_topics.VEHICLE_LOCAL_POSITION)
        self.declare_parameter(
            'vehicle_attitude_topic', px4_topics.VEHICLE_ATTITUDE)

        self.map_size_m = float(self.get_parameter('map_size_m').value)
        self.resolution = float(self.get_parameter('map_resolution').value)
        self.hfov_rad = math.radians(
            float(self.get_parameter('camera_hfov_deg').value))
        self.memory_tau_s = float(self.get_parameter('memory_tau_s').value)
        self.min_evidence = float(self.get_parameter('min_evidence').value)
        self.max_tilt_rad = math.radians(
            float(self.get_parameter('max_tilt_deg').value))
        self.map_frame = self.get_parameter('map_frame').value

        self.cells = max(1, int(round(self.map_size_m / self.resolution)))
        self.bridge = CvBridge()
        self.stage_times = {}

        # Per-cell, per-class evidence. The map is vehicle-centred and slides
        # with it, so this array is rolled to match whenever the origin moves.
        self.evidence = np.zeros(
            (self.cells, self.cells, classes.NUM_CLASSES), dtype=np.float32)
        self.origin_m = None      # (east, north) of cell (0, 0)
        self.last_fuse_time = None

        self.pos_enu = None       # (x_east, y_north, z_up)
        self.altitude_agl = None
        self.R_ned_body = None    # from VehicleAttitude
        self.camera_matrix = None  # from CameraInfo, else derived from hfov
        self.warned_no_pose = False
        self.warned_no_attitude = False
        self.frame_count = 0
        self.dropped_tilt = 0

        # id -> RGB lookup, built once. Indexing a (NUM_CLASSES, 3) array by
        # the grid turns the whole colourisation into one gather.
        self.palette = np.zeros((classes.NUM_CLASSES, 3), dtype=np.uint8)
        for cid, rgb in classes.CLASS_COLORS.items():
            self.palette[cid] = rgb
        self.publish_debug_image = bool(
            self.get_parameter('publish_debug_image').value)

        self.map_pub = self.create_publisher(
            OccupancyGrid, self.get_parameter('map_topic').value, SENSOR_QOS)
        self.debug_pub = self.create_publisher(
            Image, self.get_parameter('debug_image_topic').value, SENSOR_QOS)
        self.publish_instant_map = bool(
            self.get_parameter('publish_instant_map').value)
        self.instant_pub = self.create_publisher(
            OccupancyGrid, self.get_parameter('instant_map_topic').value,
            SENSOR_QOS)
        self.create_subscription(
            Image, self.get_parameter('mask_topic').value,
            self.on_mask, SENSOR_QOS)
        self.create_timer(10.0, self.report_stages)
        self.create_subscription(
            CameraInfo, self.get_parameter('camera_info_topic').value,
            self.on_camera_info, SENSOR_QOS)
        self.create_subscription(
            VehicleLocalPosition,
            self.get_parameter('vehicle_local_position_topic').value,
            self.on_local_position, PX4_QOS)
        self.create_subscription(
            VehicleAttitude,
            self.get_parameter('vehicle_attitude_topic').value,
            self.on_attitude, PX4_QOS)

        self.get_logger().info(
            f'mapping_node up: {self.cells}x{self.cells} cells @ '
            f'{self.resolution} m/cell ({self.map_size_m} m span), '
            f'hfov={math.degrees(self.hfov_rad):.1f} deg, '
            f'memory tau={self.memory_tau_s:.0f} s, '
            f'max tilt={math.degrees(self.max_tilt_rad):.0f} deg')

    # ------------------------------------------------------------------
    def on_local_position(self, msg: VehicleLocalPosition) -> None:
        """PX4 NED -> ENU. This is a read-only convenience; the authoritative
        ENU<->NED conversion for *commands* lives only in eland_mode."""
        self.pos_enu = (float(msg.y), float(msg.x), float(-msg.z))
        if msg.dist_bottom_valid:
            self.altitude_agl = float(msg.dist_bottom)
        else:
            self.altitude_agl = float(-msg.z)

    def on_attitude(self, msg: VehicleAttitude) -> None:
        self.R_ned_body = quaternion_to_matrix(msg.q)

    def on_camera_info(self, msg: CameraInfo) -> None:
        k = np.asarray(msg.k, dtype=np.float64).reshape(3, 3)
        if k[0, 0] > 0.0:
            self.camera_matrix = k

    def intrinsics(self, width: int, height: int) -> np.ndarray:
        """Camera matrix, from CameraInfo if it arrived, else from the FOV.

        In this simulation the fallback is what actually runs. `ros_gz_image`
        advertises /camera/camera_info for the labels_map stream but never
        publishes on it -- verified with `ros2 topic hz`, which reports nothing
        -- so the topic existing in `ros2 topic list` says only that it was
        advertised. Gazebo's own /seg_cam/camera_info reports fx = 134.984
        against the 134.7 this derives from the declared FOV, i.e. 0.2%, so
        nothing is lost by the fallback.

        The CameraInfo path is kept for the real sensor that eventually
        replaces the simulated one, where a calibrated principal point and
        focal length are not something to derive from a nominal FOV.
        """
        if self.camera_matrix is not None:
            return self.camera_matrix
        fx = (width / 2.0) / math.tan(self.hfov_rad / 2.0)
        return np.array([
            [fx, 0.0, width / 2.0],
            [0.0, fx, height / 2.0],
            [0.0, 0.0, 1.0],
        ], dtype=np.float64)

    # ------------------------------------------------------------------
    def stage(self, name, t0):
        """Record how long one stage of the frame took."""
        now = time.perf_counter()
        self.stage_times.setdefault(name, []).append(now - t0)
        return now

    def report_stages(self):
        """Where the frame time goes, p50 and p95, every report_period_s.

        Logged rather than guessed at: "the pipeline is slow" is not
        actionable, and the obvious suspect -- the projection -- is not
        always the expensive one.
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
        self.get_logger().info('frame ms (p50/p95): ' + '  '.join(parts))

    def on_mask(self, msg: Image) -> None:
        if self.pos_enu is None:
            if not self.warned_no_pose:
                self.warned_no_pose = True
                self.get_logger().warning(
                    'mask received but no VehicleLocalPosition yet -- is the '
                    'uXRCE-DDS agent running and the topic name right?')
            return
        if self.R_ned_body is None:
            if not self.warned_no_attitude:
                self.warned_no_attitude = True
                self.get_logger().warning(
                    'mask received but no VehicleAttitude yet; the projection '
                    'needs it to de-rotate the frame. Check '
                    f'"{self.get_parameter("vehicle_attitude_topic").value}".')
            return

        mask = self.bridge.imgmsg_to_cv2(msg)
        if mask.ndim == 3:
            mask = mask[:, :, 0]
        mask = np.clip(mask.astype(np.uint8), 0, classes.NUM_CLASSES - 1)

        t0 = time.perf_counter()
        self.slide_to_current_position()
        t0 = self.stage('slide', t0)
        self.decay()
        t0 = self.stage('decay', t0)
        instant = self.observe(mask)
        t0 = self.stage('project', t0)
        grid = self.fused_grid()
        t0 = self.stage('fuse', t0)
        self.publish_grid(grid, msg.header.stamp)
        if self.publish_debug_image:
            self.publish_debug(grid, msg.header.stamp)
        if self.publish_instant_map and instant is not None:
            self.publish_grid(instant, msg.header.stamp, self.instant_pub)
        self.stage('publish', t0)

    # ------------------------------------------------------------------
    def current_origin(self):
        """(east, north) world coordinate of cell (0, 0), vehicle-centred."""
        east, north, _ = self.pos_enu
        half = self.map_size_m / 2.0
        return (east - half, north - half)

    def slide_to_current_position(self) -> None:
        """Roll the accumulator so a given cell keeps meaning the same place.

        The map follows the vehicle, so between frames the origin moves and
        every cell index refers to a different patch of ground. Shifting the
        array by the integer cell delta keeps the accumulated evidence
        attached to the world rather than to the array.

        Sub-cell motion is dropped rather than interpolated: class evidence
        must not be smeared across neighbours, and at 0.2 m/cell the residual
        error stays under one cell.
        """
        new_origin = self.current_origin()
        if self.origin_m is None:
            self.origin_m = new_origin
            return

        d_east_cells = int(round((new_origin[0] - self.origin_m[0]) / self.resolution))
        d_north_cells = int(round((new_origin[1] - self.origin_m[1]) / self.resolution))
        if d_east_cells == 0 and d_north_cells == 0:
            return

        # Origin moving +east means the ground under column c is now under
        # column c - d, hence a roll of -d. Rows are north, same argument.
        if abs(d_east_cells) >= self.cells or abs(d_north_cells) >= self.cells:
            self.evidence.fill(0.0)  # jumped further than the map is wide
        else:
            self.evidence = np.roll(self.evidence, -d_east_cells, axis=1)
            self.evidence = np.roll(self.evidence, -d_north_cells, axis=0)
            # np.roll wraps; the cells that wrapped around are ground we have
            # never seen, so clear them instead of trusting the far edge.
            if d_east_cells > 0:
                self.evidence[:, -d_east_cells:, :] = 0.0
            elif d_east_cells < 0:
                self.evidence[:, :-d_east_cells, :] = 0.0
            if d_north_cells > 0:
                self.evidence[-d_north_cells:, :, :] = 0.0
            elif d_north_cells < 0:
                self.evidence[:-d_north_cells, :, :] = 0.0

        # Only advance the origin by whole cells actually applied, so the
        # dropped sub-cell remainder is carried into the next frame instead of
        # accumulating into a drift.
        self.origin_m = (self.origin_m[0] + d_east_cells * self.resolution,
                         self.origin_m[1] + d_north_cells * self.resolution)

    def decay(self) -> None:
        """Exponential forgetting, in wall-clock time rather than per frame.

        Frame-rate independence matters here: the segmentation camera runs at
        5 Hz nominal but drops frames under render load, and a per-frame decay
        constant would silently change the memory horizon whenever the
        simulation got busy.
        """
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.last_fuse_time is not None and self.memory_tau_s > 0.0:
            dt = max(0.0, now - self.last_fuse_time)
            self.evidence *= math.exp(-dt / self.memory_tau_s)
        self.last_fuse_time = now

    # ------------------------------------------------------------------
    def ground_homography(self, width: int, height: int) -> np.ndarray:
        """Image pixels -> map cells, via the ground plane.

        For a pixel ``p``, the ray direction in NED is ``M p`` with
        ``M = R_ned_body @ R_body_cam @ K^-1``. Intersecting with the ground
        ``a`` metres below the camera gives the metric point

            north = t_n + a * (Mp)_0 / (Mp)_2
            east  = t_e + a * (Mp)_1 / (Mp)_2

        and the map indices follow from the grid origin and resolution. Written
        homogeneously, with ``w = (Mp)_2``, that is a plain 3x3 homography --
        which is the whole reason a single warpPerspective can replace a
        per-pixel loop.
        """
        k_inv = np.linalg.inv(self.intrinsics(width, height))
        m = self.R_ned_body @ R_BODY_CAM @ k_inv

        alt = max(self.altitude_agl or 0.0, 0.1)
        east, north, _ = self.pos_enu
        d_east = east - self.origin_m[0]
        d_north = north - self.origin_m[1]

        scale = alt / self.resolution
        # Column index runs east, row index runs north -- the OccupancyGrid
        # origin is the south-west corner, so row 0 is the southernmost.
        col_row = scale * m[1, :] + (d_east / self.resolution - 0.5) * m[2, :]
        row_row = scale * m[0, :] + (d_north / self.resolution - 0.5) * m[2, :]
        return np.vstack([col_row, row_row, m[2, :]])

    def tilt_rad(self) -> float:
        """Angle between the body's down axis and true down."""
        return math.acos(max(-1.0, min(1.0, float(self.R_ned_body[2, 2]))))

    def observe(self, mask: np.ndarray):
        """Warp this frame onto the ground plane and add it to the accumulator.

        Returns the warped frame on its own -- cells this frame did not see
        set to UNKNOWN -- or None if the frame was dropped. That return value
        is what tracker_node sees; the accumulator it feeds is what everything
        else sees.
        """
        tilt = self.tilt_rad()
        if tilt > self.max_tilt_rad:
            self.dropped_tilt += 1
            self.get_logger().debug(
                f'frame dropped: tilt {math.degrees(tilt):.1f} deg exceeds '
                f'{math.degrees(self.max_tilt_rad):.0f} deg '
                f'({self.dropped_tilt} so far)')
            return None

        h_px, w_px = mask.shape[:2]
        homography = self.ground_homography(w_px, h_px)
        size = (self.cells, self.cells)

        # INTER_NEAREST is not a performance choice: class IDs must never be
        # interpolated, or a grass/building boundary would produce gravel.
        projected = cv2.warpPerspective(
            mask, homography, size, flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        # Warping a field of ones the same way says which cells this frame
        # actually saw, as opposed to cells the border filled in with zeros --
        # which would otherwise read as genuine observations of UNKNOWN.
        coverage = cv2.warpPerspective(
            np.ones((h_px, w_px), dtype=np.uint8), homography, size,
            flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT,
            borderValue=0)

        rows, cols = np.nonzero(coverage)
        if rows.size == 0:
            return None
        np.add.at(self.evidence, (rows, cols, projected[rows, cols]), 1.0)

        self.get_logger().debug(
            f'projected {rows.size} cells at alt {self.altitude_agl:.1f} m, '
            f'tilt {math.degrees(tilt):.1f} deg')

        # Uncovered cells carry the border fill, which is numerically UNKNOWN
        # already; masking is explicit so the intent survives a change of
        # borderValue.
        instant = np.where(coverage > 0, projected, classes.UNKNOWN)
        return instant.astype(np.uint8)

    def fused_grid(self) -> np.ndarray:
        """Winner-takes-all over the accumulated evidence.

        A cell whose total evidence has decayed below min_evidence reverts to
        UNKNOWN rather than keeping its last winner: forgetting has to produce
        "I do not know", never a stale confident answer.
        """
        total = self.evidence.sum(axis=2)
        grid = self.evidence.argmax(axis=2).astype(np.uint8)
        grid[total < self.min_evidence] = classes.UNKNOWN
        return grid

    # ------------------------------------------------------------------
    def publish_grid(self, grid: np.ndarray, stamp, pub=None) -> None:
        """Publish a class-ID grid. `pub` selects fused (default) or instant;
        both carry the same geometry, so a consumer can swap topics without
        changing a line of its own arithmetic."""
        msg = OccupancyGrid()
        msg.header.stamp = stamp
        msg.header.frame_id = self.map_frame
        msg.info.map_load_time = stamp
        msg.info.resolution = self.resolution
        msg.info.width = self.cells
        msg.info.height = self.cells

        # Publish the accumulator's own origin, not the vehicle's current one:
        # they differ by the sub-cell remainder that slide_to_current_position
        # deliberately did not apply, and the grid contents belong to the
        # former.
        msg.info.origin.position.x = self.origin_m[0]
        msg.info.origin.position.y = self.origin_m[1]
        msg.info.origin.position.z = 0.0
        msg.info.origin.orientation.w = 1.0

        # Class IDs cast to int8 -- NOT 0..100 occupancy probabilities.
        msg.data = grid.astype(np.int8).ravel().tolist()
        if pub is None:
            self.map_pub.publish(msg)
            self.frame_count += 1
        else:
            pub.publish(msg)

    def publish_debug(self, grid: np.ndarray, stamp) -> None:
        """Human-readable view of the same grid.

        RViz cannot render the ground map: its Map display expects 0..100
        occupancy and this carries class IDs, so it comes out near-black. This
        topic exists solely so a person can see what the pipeline sees.

        Flipped vertically on the way out. Grid row 0 is the OccupancyGrid
        origin row, i.e. the southernmost, while an image is drawn top row
        first -- so without the flip the debug view would be upside down
        relative to every map anyone has ever read. (That same confusion, left
        unnoticed, is what mirrored the projection itself before the IPM
        rewrite.)
        """
        rgb = self.palette[np.flipud(grid)]
        out = self.bridge.cv2_to_imgmsg(np.ascontiguousarray(rgb), encoding='rgb8')
        out.header.stamp = stamp
        out.header.frame_id = self.map_frame
        self.debug_pub.publish(out)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MappingNode()
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
