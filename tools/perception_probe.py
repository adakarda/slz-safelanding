#!/usr/bin/env python3
"""Why does the map stop offering sites when the aircraft is pushed?

Under a 15 N side force the detector reported "no cells in C_safe" and
"nothing eligible" for 125-157 consecutive frames and the landing was lost --
while the vertical loop kept tracking its reference. That says the envelope is
set by perception rather than by control, but not *which* part of perception,
and there are two candidates that call for different fixes:

  tilt   a side force needs a steady bank, and a downward camera on a banked
         aircraft looks somewhere else. The projection does use attitude, so
         the geometry is right -- but the footprint still slides off the
         mapped window, and rays near the horizon land far away or nowhere.

  speed  a dragged aircraft sweeps new ground every frame, and the fused map
         needs several frames of evidence per cell before a class settles.

This samples both maps' class histograms alongside tilt and ground speed, then
bins the unknown fraction by each, so the two can be told apart instead of
argued about.
"""
import sys
import time

import numpy as np
import rclpy
from nav_msgs.msg import OccupancyGrid
from px4_msgs.msg import VehicleAttitude, VehicleLocalPosition
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)

SENSOR_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                        durability=DurabilityPolicy.VOLATILE,
                        history=HistoryPolicy.KEEP_LAST, depth=1)
PX4_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     history=HistoryPolicy.KEEP_LAST, depth=1)
UNKNOWN = 7
SAFE = (0, 1)
TILT_BINS = (0.0, 5.0, 10.0, 20.0, 30.0, 90.0)
SPEED_BINS = (0.0, 1.0, 3.0, 6.0, 100.0)


class Probe(Node):
    def __init__(self, duration):
        super().__init__('perception_probe')
        self.duration = duration
        self.t0 = time.time()
        self.tilt_deg = 0.0
        self.speed = 0.0
        self.alt = 0.0
        self.rows = []      # (tilt, speed, alt, unknown_frac, safe_frac)
        self.inst = []      # same, for the unfused map
        self.create_subscription(VehicleAttitude, '/fmu/out/vehicle_attitude',
                                 self.on_att, PX4_QOS)
        self.create_subscription(VehicleLocalPosition,
                                 '/fmu/out/vehicle_local_position_v1',
                                 self.on_pos, PX4_QOS)
        self.create_subscription(OccupancyGrid, '/eland/ground_map',
                                 self.on_fused, SENSOR_QOS)
        self.create_subscription(OccupancyGrid, '/eland/ground_map_instant',
                                 self.on_instant, SENSOR_QOS)
        self.create_timer(1.0, self.tick)

    def on_att(self, msg):
        # Tilt is the angle between the body down axis and world down, which
        # is what the third diagonal term of the rotation matrix carries.
        w, x, y, z = (float(msg.q[0]), float(msg.q[1]), float(msg.q[2]),
                      float(msg.q[3]))
        r22 = 1.0 - 2.0 * (x * x + y * y)
        self.tilt_deg = float(np.degrees(np.arccos(np.clip(r22, -1.0, 1.0))))

    def on_pos(self, msg):
        self.speed = float(np.hypot(msg.vx, msg.vy))
        self.alt = -float(msg.z)

    def _sample(self, msg, sink):
        g = np.asarray(msg.data, dtype=np.int16)
        if g.size == 0:
            return
        sink.append((self.tilt_deg, self.speed, self.alt,
                     float((g == UNKNOWN).mean()),
                     float(np.isin(g, SAFE).mean())))

    def on_fused(self, msg):
        self._sample(msg, self.rows)

    def on_instant(self, msg):
        self._sample(msg, self.inst)

    def tick(self):
        if time.time() - self.t0 < self.duration:
            return
        self.report()
        raise SystemExit(0)

    def report(self):
        for name, data in (('fuzyonlu harita', self.rows),
                           ('anlik harita', self.inst)):
            if not data:
                print(f'{name}: kare yok')
                continue
            a = np.asarray(data)
            print(f'--- {name} ({len(a)} kare) ---')
            print(f'  bilinmeyen orani ortalama {a[:, 3].mean():.2f}, '
                  f'guvenli sinif orani ortalama {a[:, 4].mean():.2f}')
            print('  egim [deg]   kare   bilinmeyen   guvenli')
            for lo, hi in zip(TILT_BINS, TILT_BINS[1:]):
                m = (a[:, 0] >= lo) & (a[:, 0] < hi)
                if m.sum() < 3:
                    continue
                print(f'   {lo:4.0f}-{hi:<4.0f}   {int(m.sum()):5d}   '
                      f'{a[m, 3].mean():9.2f}   {a[m, 4].mean():7.2f}')
            print('  hiz [m/s]    kare   bilinmeyen   guvenli')
            for lo, hi in zip(SPEED_BINS, SPEED_BINS[1:]):
                m = (a[:, 1] >= lo) & (a[:, 1] < hi)
                if m.sum() < 3:
                    continue
                print(f'   {lo:4.1f}-{hi:<4.1f}   {int(m.sum()):5d}   '
                      f'{a[m, 3].mean():9.2f}   {a[m, 4].mean():7.2f}')
        if self.rows:
            a = np.asarray(self.rows)
            print(f'egim aralik {a[:, 0].min():.1f}-{a[:, 0].max():.1f} deg, '
                  f'hiz {a[:, 1].min():.1f}-{a[:, 1].max():.1f} m/s, '
                  f'irtifa {a[:, 2].min():.1f}-{a[:, 2].max():.1f} m')


def main():
    rclpy.init()
    n = Probe(float(sys.argv[1]) if len(sys.argv) > 1 else 90.0)
    try:
        rclpy.spin(n)
    except SystemExit:
        pass
    finally:
        n.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
