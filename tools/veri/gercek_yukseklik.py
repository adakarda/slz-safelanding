#!/usr/bin/env python3
"""Ground-truth height above the surface under the aircraft, for the 'kahin' law.

    tools/veri/gercek_yukseklik.py --dunya-yaml Y --gz-world W --model M

SIMULATION ONLY: a reference the mode can be switched to (inis_yasasi:
kahin), never a sensor. Publishes /eland/sim/h_gercek (std_msgs/Float32, m) at
up to 50 Hz: Gazebo model z minus the height of whatever surface is under
the model (tools/veri/dunya.py, from the world's yaml) minus the model's
resting offset, i.e. 0 at rest on the surface -- the same convention as the
mode's altitude and kaydedici.py's h_gercek_zemin.

The resting offset is measured on the ground before take-off (the first
landed pose), as politika.py does; until then the 2026-10-03 value is used.
run_sim.sh starts it with RUN_SIM_INIS_YASASI=1.
"""
import argparse
import os
import sys

import rclpy
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node as GzNode
from px4_msgs.msg import VehicleLandDetected
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float32

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dunya import Dunya  # noqa: E402

Z_DINLENME_VARSAYILAN = -0.013   # politika.py, kaydedici.py (2026-10-03, measured)
BEST_EFFORT = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE,
                         history=HistoryPolicy.KEEP_LAST, depth=5)


class GercekYukseklik(Node):
    def __init__(self, a):
        super().__init__('gercek_yukseklik')
        self.a = a
        self.dw = Dunya(a.dunya_yaml)
        self.z_rest = None
        self.landed = None
        self.h = float('nan')
        self.yeni = False
        self.pub = self.create_publisher(Float32, a.topic, BEST_EFFORT)
        self.create_timer(0.02, self.tick)
        self.create_subscription(VehicleLandDetected, '/fmu/out/vehicle_land_detected',
                                 self.on_land, BEST_EFFORT)
        self.gz = GzNode()
        topic = f'/world/{a.gz_world}/dynamic_pose/info'
        if not self.gz.subscribe(Pose_V, topic, self.on_pose):
            self.get_logger().error(f'{topic} dinlenemedi')
        self.get_logger().info(f'kahin: {a.model} in {a.gz_world} -> {a.topic} (yalniz simulasyon)')

    def on_land(self, msg):
        self.landed = bool(msg.landed)

    def on_pose(self, msg):
        # gz-transport calls this from its own thread: only store here, and
        # publish from the ROS timer, as politika.py does.
        for p in msg.pose:
            if p.name != self.a.model:
                continue
            x, y, z = p.position.x, p.position.y, p.position.z
            zemin = self.dw.yuzey_z(x, y)
            if self.z_rest is None and self.landed:
                self.z_rest = z - zemin
                self.get_logger().info(f'dinlenme ofseti olculdu: {self.z_rest:+.3f} m')
            z_rest = self.z_rest if self.z_rest is not None else Z_DINLENME_VARSAYILAN
            self.h = float(z - zemin - z_rest)
            self.yeni = True
            return

    def tick(self):
        if self.yeni:
            self.yeni = False
            self.pub.publish(Float32(data=self.h))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--dunya-yaml', required=True)
    p.add_argument('--gz-world', required=True)
    p.add_argument('--model', required=True, help='Gazebo model name, e.g. x500_seg_cam_down_0')
    p.add_argument('--topic', default='/eland/sim/h_gercek')
    a = p.parse_args()
    rclpy.init()
    node = GercekYukseklik(a)
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
