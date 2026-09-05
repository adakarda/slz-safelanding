#!/usr/bin/env python3
"""How well is the commanded descent speed actually followed?

The mode computes a vertical speed and hands it to PX4 as the *limit* of a
goto setpoint, so nothing in the loop compares what was asked for with what
happened. This measures that gap, plus the two things a controller chapter
would have to answer for: how often the law switches between its area branch
and its altitude branch, and how big the command jumps when it does.
"""
import sys
import time

import numpy as np
import rclpy
from eland_msgs.msg import LandingState
from px4_msgs.msg import VehicleLocalPosition
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)

DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                          durability=DurabilityPolicy.VOLATILE,
                          history=HistoryPolicy.KEEP_LAST, depth=1)
PX4_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     history=HistoryPolicy.KEEP_LAST, depth=1)
NAMES = {0: 'SEARCH', 1: 'APPROACH', 2: 'VALIDATE', 3: 'HOLD', 4: 'ABORT',
         5: 'COMMIT'}


class Probe(Node):
    def __init__(self, duration):
        super().__init__('descent_probe')
        self.duration = duration
        self.t0 = time.time()
        self.vz = 0.0          # NED: positive down
        self.rows = []         # (t, state, alt, commanded, achieved)
        self.create_subscription(VehicleLocalPosition,
                                 '/fmu/out/vehicle_local_position_v1',
                                 self.on_pos, PX4_QOS)
        self.create_subscription(LandingState, '/eland/state', self.on_state,
                                 DECISION_QOS)
        self.create_timer(1.0, self.tick)

    def on_pos(self, msg):
        self.vz = float(msg.vz)

    def on_state(self, msg):
        self.rows.append((time.time(), int(msg.state), float(msg.altitude_agl),
                          float(msg.commanded_descent_mps), self.vz))

    def tick(self):
        if time.time() - self.t0 < self.duration:
            return
        rows = [r for r in self.rows if r[1] in (2, 5) and r[3] > 0.0]
        if not rows:
            print('inis verisi yok')
            raise SystemExit(0)
        cmd = np.array([r[3] for r in rows])
        got = np.array([r[4] for r in rows])
        err = got - cmd
        print(f'orneklem {len(rows)} (VALIDATE + COMMIT)')
        print(f'komut edilen dikey hiz : ortalama {cmd.mean():.2f} m/s, '
              f'aralik {cmd.min():.2f}-{cmd.max():.2f}')
        print(f'gerceklesen            : ortalama {got.mean():.2f} m/s, '
              f'aralik {got.min():.2f}-{got.max():.2f}')
        print(f'takip hatasi (ger-kom) : ortalama {err.mean():+.2f} m/s, '
              f'mutlak ortalama {np.abs(err).mean():.2f}, '
              f'en buyuk {np.abs(err).max():.2f}')
        print(f'komutun altinda kalinan orneklerin orani '
              f'{100.0 * (got < cmd - 0.1).mean():.0f} %')
        # Split by altitude. A shortfall that only appears in the last few
        # metres is PX4 decelerating into its position setpoint, which is
        # correct behaviour; a shortfall present at every height is an open
        # loop that never tracked its own command.
        alt = np.array([r[2] for r in rows])
        print('irtifa bandi   komut   gerceklesen   hata')
        for lo, hi in ((10.0, 99.0), (5.0, 10.0), (2.0, 5.0), (0.0, 2.0)):
            m = (alt >= lo) & (alt < hi)
            if not m.any():
                continue
            print(f'  {lo:4.0f}-{hi:<4.0f} m   {cmd[m].mean():5.2f}   '
                  f'{got[m].mean():9.2f}   {err[m].mean():+5.2f}  '
                  f'({int(m.sum())} ornek)')
        # Descent-phase duration only. Mode activation to touchdown also
        # contains SEARCH and APPROACH, which vary by several seconds between
        # runs of the same configuration and swamp the difference being
        # measured here.
        t = np.array([r[0] for r in rows])
        print(f'alcalma suresi (ilk VALIDATE -> son ornek): '
              f'{t[-1] - t[0]:.1f} s')
        print(f'RMS takip hatasi: {float(np.sqrt(np.mean(err ** 2))):.3f} m/s')
        jumps = np.abs(np.diff(cmd))
        big = int((jumps > 0.3).sum())
        print(f'komut sicramasi        : {big} kez 0.3 m/s ustu, '
              f'en buyugu {jumps.max():.2f} m/s')
        raise SystemExit(0)


rclpy.init()
n = Probe(float(sys.argv[1]) if len(sys.argv) > 1 else 100.0)
try:
    rclpy.spin(n)
except SystemExit:
    pass
finally:
    n.destroy_node()
    rclpy.try_shutdown()
