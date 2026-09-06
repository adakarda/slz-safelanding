#!/usr/bin/env python3
"""Score one flight: decision loop, vertical rate tracking, outcome.

Replaces the earlier descent_probe.py. One scorer rather than two, because
two scripts measuring the same run from the same topics drift apart the first
time only one of them is fixed.

Prints a human table and, after it, one `key=value` line per metric so a batch
runner can collect them without parsing prose.

Finishes on its own when the aircraft touches down (COMMIT, then the state
channel goes quiet), so a batch of runs costs what the flights cost rather
than a fixed window each.
"""
import sys
import time

import numpy as np
import rclpy
from eland_msgs.msg import LandingCandidate, LandingState
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
VALIDATE, COMMIT = 2, 5
JUMP_M = 4.0
QUIET_S = 3.0      # state channel silent this long after COMMIT = landed
BANDS = ((10.0, 99.0), (5.0, 10.0), (2.0, 5.0), (0.0, 2.0))


class Scorer(Node):
    def __init__(self, timeout_s):
        super().__init__('run_scorer')
        self.timeout_s = timeout_s
        self.t0 = time.time()
        self.vz = 0.0                  # NED, down positive
        self.rows = []                 # (t, state, alt, commanded, achieved)
        self.states = []
        self.state_t = None
        self.cand_t = []
        self.invalid = 0
        self.streaks = []
        self.bad_since = None
        self.jumps = 0
        self.last_site = None
        self.seen_commit = False
        # "Landed" only says the land detector fired. What the site was, and
        # whether the aircraft actually came down on it, is a separate
        # question -- and it is the one a safety argument rests on.
        self.last_valid = None
        self.pos = None
        self.touchdown_pos = None
        self.create_subscription(VehicleLocalPosition,
                                 '/fmu/out/vehicle_local_position_v1',
                                 self.on_pos, PX4_QOS)
        self.create_subscription(LandingState, '/eland/state', self.on_state,
                                 DECISION_QOS)
        self.create_subscription(LandingCandidate, '/eland/candidate',
                                 self.on_cand, DECISION_QOS)
        self.create_timer(0.5, self.tick)

    # -- inputs --------------------------------------------------------
    def on_pos(self, msg):
        self.vz = float(msg.vz)
        # ENU-ish for comparison with the candidate: the candidate is published
        # in map frame (x east, y north), the estimate is NED.
        self.pos = (float(msg.y), float(msg.x))

    def on_state(self, msg):
        now = time.time()
        self.state_t = now
        s = int(msg.state)
        if not self.states or self.states[-1] != s:
            self.states.append(s)
        if s == COMMIT:
            self.seen_commit = True
            if self.pos is not None:
                self.touchdown_pos = self.pos  # last one wins
        self.rows.append((now, s, float(msg.altitude_agl),
                          float(msg.commanded_descent_mps), self.vz))

    def on_cand(self, msg):
        now = time.time()
        self.cand_t.append(now)
        if not msg.valid:
            self.invalid += 1
            if self.bad_since is None:
                self.bad_since = now
            return
        if self.bad_since is not None:
            self.streaks.append(now - self.bad_since)
            self.bad_since = None
        site = (msg.position.x, msg.position.y)
        if self.last_site is not None:
            if float(np.hypot(site[0] - self.last_site[0],
                              site[1] - self.last_site[1])) > JUMP_M:
                self.jumps += 1
        self.last_site = site
        self.last_valid = msg

    # -- finishing -----------------------------------------------------
    def tick(self):
        landed = (self.seen_commit and self.state_t is not None
                  and time.time() - self.state_t > QUIET_S)
        if landed or time.time() - self.t0 > self.timeout_s:
            self.report(landed)
            raise SystemExit(0)

    def report(self, landed):
        out = {'landed': int(bool(landed))}

        n = len(self.cand_t)
        span = self.cand_t[-1] - self.cand_t[0] if n > 1 else 0.0
        out['candidate_hz'] = round((n - 1) / span, 3) if span > 0 else 0.0
        out['candidate_msgs'] = n
        out['invalid_frames'] = self.invalid
        out['gaps_over_3s'] = sum(1 for d in self.streaks if d >= 3.0)
        out['site_jumps'] = self.jumps
        out['transitions'] = max(0, len(self.states) - 1)
        out['aborts'] = sum(1 for s in self.states if s == 4)
        print(f'aday          : {n} mesaj, {out["candidate_hz"]:.2f} Hz, '
              f'{self.invalid} gecersiz, {out["gaps_over_3s"]} bosluk >3 s, '
              f'{self.jumps} sicrama >{JUMP_M:.0f} m')
        print(f'durum gecisi  : {out["transitions"]} '
              f'({" -> ".join(NAMES.get(s, str(s)) for s in self.states[:12])})')

        if self.last_valid is not None:
            out['site_risk'] = round(float(self.last_valid.risk_score), 3)
            out['site_clearance_m'] = round(float(self.last_valid.radius), 2)
            out['site_area_m2'] = round(float(self.last_valid.area_m2), 1)
            if self.touchdown_pos is not None and self.last_site is not None:
                out['touchdown_err_m'] = round(float(np.hypot(
                    self.touchdown_pos[0] - self.last_site[0],
                    self.touchdown_pos[1] - self.last_site[1])), 2)
            print(f'inis yeri     : risk {out["site_risk"]:.2f}, aciklik '
                  f'{out["site_clearance_m"]:.1f} m, alan '
                  f'{out["site_area_m2"]:.0f} m2, dokunma sapmasi '
                  f'{out.get("touchdown_err_m", float("nan")):.2f} m')

        rows = [r for r in self.rows if r[1] in (VALIDATE, COMMIT) and r[3] > 0.0]
        if rows:
            t = np.array([r[0] for r in rows])
            alt = np.array([r[2] for r in rows])
            cmd = np.array([r[3] for r in rows])
            got = np.array([r[4] for r in rows])
            err = got - cmd
            out['descent_s'] = round(float(t[-1] - t[0]), 2)
            out['err_mean'] = round(float(err.mean()), 3)
            out['err_abs_mean'] = round(float(np.abs(err).mean()), 3)
            out['err_rms'] = round(float(np.sqrt(np.mean(err ** 2))), 3)
            print(f'alcalma       : {out["descent_s"]:.1f} s, takip hatasi '
                  f'ortalama {out["err_mean"]:+.2f}, RMS {out["err_rms"]:.3f} m/s')
            print('irtifa bandi   komut   gerceklesen   hata')
            for lo, hi in BANDS:
                m = (alt >= lo) & (alt < hi)
                if not m.any():
                    continue
                key = f'err_{int(lo)}_{int(hi)}'
                out[key] = round(float(err[m].mean()), 3)
                print(f'  {lo:4.0f}-{hi:<4.0f} m   {cmd[m].mean():5.2f}   '
                      f'{got[m].mean():9.2f}   {err[m].mean():+5.2f}  '
                      f'({int(m.sum())} ornek)')
        else:
            out['descent_s'] = 0.0

        print('--- makine okunur ---')
        for k, v in out.items():
            print(f'{k}={v}')


def main():
    rclpy.init()
    node = Scorer(float(sys.argv[1]) if len(sys.argv) > 1 else 180.0)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
