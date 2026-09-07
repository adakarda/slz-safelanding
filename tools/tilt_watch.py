#!/usr/bin/env python3
"""Live tilt and drift, for watching a disturbance run with your own eyes.

The window shows the aircraft leaning; it does not say by how much, and the
number is the point: a side force of F newtons on a 2 kg airframe needs a bank
of atan(F / (m g)) to hold station -- 27 degrees at 10 N, 37 at 15 -- and past
about 30 the downward camera has lost a third of its ground coverage
(docs/TEZ_NOTLARI.md 2.9). Printed next to the drift so the two can be seen
happening together.
"""
import sys
import time

import numpy as np
import rclpy
from px4_msgs.msg import VehicleAttitude, VehicleLocalPosition
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)

PX4_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     history=HistoryPolicy.KEEP_LAST, depth=1)


class Watch(Node):
    def __init__(self, period_s):
        super().__init__('tilt_watch')
        self.tilt = 0.0
        self.pos = None
        self.origin = None
        self.alt = 0.0
        self.create_subscription(VehicleAttitude, '/fmu/out/vehicle_attitude',
                                 self.on_att, PX4_QOS)
        self.create_subscription(VehicleLocalPosition,
                                 '/fmu/out/vehicle_local_position_v1',
                                 self.on_pos, PX4_QOS)
        self.create_timer(period_s, self.tick)

    def on_att(self, msg):
        x, y = float(msg.q[1]), float(msg.q[2])
        r22 = 1.0 - 2.0 * (x * x + y * y)
        self.tilt = float(np.degrees(np.arccos(np.clip(r22, -1.0, 1.0))))

    def on_pos(self, msg):
        self.pos = (float(msg.x), float(msg.y))
        self.alt = -float(msg.z)
        if self.origin is None and self.alt > 3.0:
            # Zeroed once airborne, so the number is drift under the force
            # rather than the distance flown from the launch point.
            self.origin = self.pos

    def tick(self):
        if self.pos is None:
            return
        drift = 0.0
        if self.origin is not None:
            drift = float(np.hypot(self.pos[0] - self.origin[0],
                                   self.pos[1] - self.origin[1]))
        bar = '#' * min(40, int(self.tilt))
        print(f'yatis {self.tilt:5.1f} deg  kayma {drift:6.2f} m  '
              f'irtifa {self.alt:5.1f} m  {bar}', flush=True)


def main():
    rclpy.init()
    n = Watch(float(sys.argv[1]) if len(sys.argv) > 1 else 0.5)
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    finally:
        n.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
