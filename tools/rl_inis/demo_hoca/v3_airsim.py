#!/usr/bin/env python3
"""v3 node for AirSim: RGB camera -> v3 -> the landing pipeline, with live scoring.

    ~/v3_test/venv/bin/python -P ~/v3_test/v3_airsim.py      (run_airsim.sh --v3 starts it)

The AirSim twin of v3_golge.py. Same outputs, same model call, v3 itself unchanged:
  /eland/v3/etiket   mono8 320x240, label = class + 1. run_airsim.sh --v3 points perception_node's
                     segmentation_topic here, so the detector, the map, the landing site and the HUD
                     run on v3 instead of AirSim's ground truth. No code in the pipeline changes.
  /eland/v3/maske    mono8 at camera size, simulator classes 0..6
  /eland/v3/panel    rgb8: camera with v3's mask | ground truth | class legend and live scores

Ground truth: AirSim's own segmentation of the same frame (/camera/segmentation from airsim_kopru,
class + 1, 0 = unknown), matched to the RGB frame by stamp: the bridge stamps both images of one
simGetImages call alike. Unknown pixels are not scored.
"""
import collections
import importlib.util
import math
import threading
import time

import cv2
import numpy as np
import rclpy
from px4_msgs.msg import VehicleLocalPosition
from rclpy.executors import ExternalShutdownException
from sensor_msgs.msg import Image

from eland_common import classes, px4_topics
from eland_common.qos import PX4_QOS, SENSOR_QOS

# the Gazebo node's loader, scores and panel, reused as they are (its gz imports are not needed here,
# so they are stubbed before the module is loaded)
import sys
import types

for _m in ('gz', 'gz.msgs10', 'gz.msgs10.pose_v_pb2', 'gz.transport13'):
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.modules['gz.msgs10.pose_v_pb2'].Pose_V = object
sys.modules['gz.transport13'].Node = object
_spec = importlib.util.spec_from_file_location('v3_golge', '/home/arda/v3_test/v3_golge.py')
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)
M = G.M
NC = G.NC


class V3AirSim(G.V3Golge):
    def __init__(self):  # noqa: D107 -- the parent's __init__ is Gazebo-only; set up from scratch
        G.Node.__init__(self, 'v3_airsim')
        p = self.declare_parameter
        p('image_topic', '/camera/image')
        p('gt_topic', '/camera/segmentation')
        p('model_path', '/home/arda/v3_test/model/best_v3.pth')
        p('model_adi', 'v3')                 # panel title; e.g. v4 for best_v4.pth
        p('gsd_olcekle', True)
        p('hfov_deg', 99.7)
        p('kamera_ofseti_m', 0.10)
        p('min_yukseklik_m', 1.0)
        g = lambda k: self.get_parameter(k).value  # noqa: E731
        self.gsd_olcekle = g('gsd_olcekle')
        self.hfov = math.radians(g('hfov_deg'))
        self.tan = math.tan(self.hfov / 2)
        self.ofset, self.min_h = g('kamera_ofseti_m'), g('min_yukseklik_m')
        t0 = time.time()
        self.model = G.yukle(g('model_path'))
        self.get_logger().info(f'{g("model_adi")} yuklendi: {g("model_path")} ({self.model.cihaz}, {time.time() - t0:.1f} s); '
                               f'{g("image_topic")} -> v3 -> /eland/v3/etiket -> perception_node')
        self.son = None
        self.kilit = threading.Lock()
        self.olay = threading.Event()
        self.h = None
        self.gtler = collections.OrderedDict()           # stamp ns -> labels (class + 1)
        self.pk = threading.Lock()
        self.say, self.sure = 0, 0.0
        self.cm_son = collections.deque(maxlen=50)
        self.cm_tum = np.zeros((NC, NC), np.int64)
        self.son_ms = math.nan
        self.create_subscription(Image, g('image_topic'), self.on_img, SENSOR_QOS)
        self.create_subscription(Image, g('gt_topic'), self.on_gt, SENSOR_QOS)
        self.create_subscription(VehicleLocalPosition, px4_topics.VEHICLE_LOCAL_POSITION, self.on_lp, PX4_QOS)
        self.pub_et = self.create_publisher(Image, '/eland/v3/etiket', SENSOR_QOS)
        self.pub_m = self.create_publisher(Image, '/eland/v3/maske', SENSOR_QOS)
        self.pub_p = self.create_publisher(Image, '/eland/v3/panel', 1)   # reliable: rqt_image_view does not take best effort
        self.create_timer(5.0, self.rapor)
        threading.Thread(target=self.dongu, daemon=True).start()

    def on_gt(self, msg):
        a = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)[:, :msg.width]
        with self.pk:
            self.gtler[msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec] = a.copy()
            while len(self.gtler) > 30:
                self.gtler.popitem(last=False)

    def gt_kare(self, t, w, h):
        """AirSim's labels of the frame stamped t (s), at w x h; 255 = unknown or no matching frame."""
        ns = round(t * 1e9)
        with self.pk:
            hit = next((v for k, v in self.gtler.items() if abs(k - ns) < 1_000_000), None)
        if hit is None:
            return None
        lab = cv2.resize(hit, (w, h), interpolation=cv2.INTER_NEAREST)
        return np.where(lab == 0, 255, lab.astype(np.int16) - classes.GZ_LABEL_OFFSET).astype(np.uint8)

    def panel(self, rgb, maske, gt, cm_kare):
        pan = G.V3Golge.panel(self, rgb, maske, gt, cm_kare)
        # the parent labels the right half as the photo's mask; here it is AirSim's segmentation
        w = maske.shape[1]
        cv2.rectangle(pan, (5, 5), (w - 5, 36), (0, 0, 0), -1)
        cv2.putText(pan, f'{self.get_parameter("model_adi").value} (inisi bu yonetiyor)', (10, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.rectangle(pan, (w + 5, 5), (2 * w - 5, 36), (0, 0, 0), -1)
        cv2.putText(pan, 'GT (AirSim segmentasyonu)', (w + 10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (255, 255, 255), 2, cv2.LINE_AA)
        return pan


def main():
    rclpy.init()
    node = V3AirSim()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
