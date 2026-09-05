#!/usr/bin/env python3
"""Semantic segmentation front-end for the SLZ pipeline.

Consumes camera frames and emits a ``mono8`` semantic mask whose pixel values
are the class IDs from :mod:`eland_common.classes`. This node emits class IDs
**only** -- no risk values. Risk mapping belongs to ``detector_node``.
"""

import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import Image
from eland_common import classes
from eland_common.qos import SENSOR_QOS


class PerceptionNode(Node):
    """Camera image -> semantic mask (class IDs)."""

    def __init__(self) -> None:
        super().__init__('perception_node')

        self.declare_parameter('use_gt_segmentation', True)
        self.declare_parameter('model_path', '')
        self.declare_parameter('input_size', [512, 512])
        self.declare_parameter('max_rate_hz', 5.0)
        self.declare_parameter('image_topic', '/camera/image')
        self.declare_parameter('segmentation_topic', '/camera/segmentation')
        self.declare_parameter('mask_topic', '/eland/semantic_mask')

        self.use_gt = self.get_parameter('use_gt_segmentation').value
        self.model_path = self.get_parameter('model_path').value
        self.input_size = [int(v) for v in self.get_parameter('input_size').value]
        self.max_rate_hz = float(self.get_parameter('max_rate_hz').value)
        self.mask_topic = self.get_parameter('mask_topic').value

        self.min_period_s = 1.0 / self.max_rate_hz if self.max_rate_hz > 0.0 else 0.0
        self.bridge = CvBridge()
        self.last_pub_time = None
        self.frame_count = 0
        self.gt_frames_seen = 0
        self.warned_no_gt = False

        # This node is the only one using a MultiThreadedExecutor, so guard the
        # single callback with a mutually exclusive group: inference is not
        # reentrant and we only ever want one frame in flight.
        self.cb_group = MutuallyExclusiveCallbackGroup()

        self.mask_pub = self.create_publisher(Image, self.mask_topic, SENSOR_QOS)

        if self.use_gt:
            source = self.get_parameter('segmentation_topic').value
        else:
            source = self.get_parameter('image_topic').value
        self.source_topic = source
        self.image_sub = self.create_subscription(
            Image, source, self.on_image, SENSOR_QOS,
            callback_group=self.cb_group)

        if not self.use_gt:
            # STUB: load the trained segmentation model from `model_path` and
            # run inference resized to `input_size`. For now on_image() returns
            # a synthetic mask instead.
            self.get_logger().info(
                f'segmentation model NOT loaded (stub); model_path='
                f'"{self.model_path}" input_size={self.input_size}')

        self.get_logger().info(
            f'perception_node up: use_gt_segmentation={self.use_gt} '
            f'source={self.source_topic} -> {self.mask_topic} '
            f'@ max {self.max_rate_hz:.1f} Hz')

        if self.use_gt:
            # Fires once if the GT topic never produces anything, which is the
            # common failure when the Gazebo model has no segmentation sensor.
            self.gt_watchdog = self.create_timer(
                5.0, self.check_gt_alive, callback_group=self.cb_group)

    # ------------------------------------------------------------------
    def check_gt_alive(self) -> None:
        """Warn once if use_gt_segmentation is on but no GT frames arrive."""
        if self.gt_frames_seen == 0 and not self.warned_no_gt:
            self.warned_no_gt = True
            self.get_logger().warning(
                f'use_gt_segmentation=true but no frames on "{self.source_topic}" '
                f'after 5 s. The Gazebo model needs a segmentation camera sensor '
                f'publishing there, or set use_gt_segmentation:=false to use the '
                f'synthetic stub mask.')
        if self.gt_frames_seen > 0:
            self.gt_watchdog.cancel()

    def throttled(self) -> bool:
        """True if the last publish was more recent than 1/max_rate_hz."""
        now = self.get_clock().now()
        if self.last_pub_time is None:
            return False
        elapsed = (now - self.last_pub_time).nanoseconds * 1e-9
        return elapsed < self.min_period_s

    # ------------------------------------------------------------------
    def on_image(self, msg: Image) -> None:
        if self.use_gt:
            self.gt_frames_seen += 1
        if self.throttled():
            return

        try:
            if self.use_gt:
                mask = self.remap_gt(msg)
            else:
                mask = self.synthetic_mask(msg.height, msg.width)
        except Exception as exc:  # noqa: BLE001 - never kill the pipeline
            self.get_logger().error(f'mask generation failed: {exc}')
            return

        out = self.bridge.cv2_to_imgmsg(mask, encoding='mono8')
        out.header = msg.header
        if not out.header.frame_id:
            out.header.frame_id = 'camera_link'
        self.mask_pub.publish(out)

        self.last_pub_time = self.get_clock().now()
        self.frame_count += 1
        self.get_logger().debug(
            f'mask #{self.frame_count} {mask.shape[1]}x{mask.shape[0]} '
            f'classes={sorted(np.unique(mask).tolist())}')

    # ------------------------------------------------------------------
    def remap_gt(self, msg: Image) -> np.ndarray:
        """Passthrough path: Gazebo ground-truth labels -> our class IDs.

        The remap is a subtraction, and the offset it undoes is the only
        translation in the project.

        The mask carries the segmentation model's own class indices, 0..6, so
        that simulator ground truth and model output can be compared without a
        lookup table. But Gazebo returns label 0 for anything unlabelled, and
        index 0 is safe-soft: with no offset, the sky, an unlabelled model and
        every labelling mistake would read as the safest ground in the world.
        So the world writes `index + 1` and this subtracts it, which leaves
        Gazebo's 0 free to mean UNKNOWN -- not landable, which is the safe
        direction to fail in.

        The offset therefore exists in exactly two places: gen_world.py and
        the template, which write the labels, and here, which reads them.
        """
        raw = self.bridge.imgmsg_to_cv2(msg)
        if raw.ndim == 3:
            # Verified against gz-sim 8.11: semantic segmentation publishes
            # rgb8 with the label replicated across all three channels. Taking
            # the red one is arbitrary but stable.
            raw = raw[:, :, 0]
        raw = raw.astype(np.uint8)
        mask = np.empty_like(raw)
        # 0 is Gazebo's "no label", which is the one value that must not map
        # into the taxonomy.
        unlabelled = raw == 0
        mask[unlabelled] = classes.UNKNOWN
        mask[~unlabelled] = raw[~unlabelled] - classes.GZ_LABEL_OFFSET
        # Anything outside the known ID range is untrusted -> unknown.
        mask[mask >= classes.NUM_CLASSES] = classes.UNKNOWN
        return np.ascontiguousarray(mask)

    def synthetic_mask(self, height: int, width: int) -> np.ndarray:
        """STUB: stand-in for trained-model inference.

        Left half grass, right half building, a 40 px circle of person at the
        image centre -- enough structure for the detector to produce a
        non-degenerate candidate on the left side.
        """
        mask = np.full((height, width), classes.SAFE_SOFT, dtype=np.uint8)
        mask[:, width // 2:] = classes.STRUCTURE

        cy, cx = height // 2, width // 2
        yy, xx = np.ogrid[:height, :width]
        circle = (yy - cy) ** 2 + (xx - cx) ** 2 <= 40 ** 2
        mask[circle] = classes.PERSON
        return mask


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PerceptionNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
