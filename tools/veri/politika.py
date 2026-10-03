#!/usr/bin/env python3
"""Speed patterns for the data-collection mode (Asama 4: K1-K4).

Publishes, at 50 Hz:
    /eland/veri/v_ref            std_msgs/Float32, m/s, down positive
    /eland/veri/h_gercek_hedef   std_msgs/Float32, m, ground-truth height
                                 above the target surface

The flight mode uses them only with `veri_toplama_kipi: true`: v_ref replaces
the descent law's output as the reference its PI tracks during VALIDATE, and
a height under `veri_devir_irtifasi` (2.5 m) hands over to the ordinary
COMMIT. Ground truth comes from Gazebo, so this is simulation only.

Patterns (`kip`), all kept inside [0.3, 1.5] m/s:
    sabit     --hiz V                      constant (K1)
    kahin     --d D                        D * h_gercek_hedef, oracle
                                           constant divergence (K2)
    rastgele  --varyant parca|carpan       RL exploration (K3): piecewise
                                           constant, pieces 0.5-2.0 s, value
                                           U[0.3, 1.5]; or the descent law
                                           times a piecewise factor U[0.5, 1.5]
    k4                                     identification from 40 m (K4): one
                                           20 s multisine round and one 20 s
                                           step round around 0.9 +- 0.6 m/s,
                                           never clipped; order alternates with
                                           the seed. Then 0.3 m/s.

`--devir-yok --son-hiz 0.5` (W5): never publish the height, so the mode never
hands over; under 2.5 m command a constant 0.5 m/s instead. Touchdown on the
platform is then measured from Gazebo by the recorder.

Patterns start when the mode enters VALIDATE.
"""
import argparse
import math
import os
import random
import sys

import numpy as np
import rclpy
import rclpy.executors
from eland_msgs.msg import LandingCandidate, LandingState
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node as GzNode
from px4_msgs.msg import VehicleLandDetected, VehicleLocalPosition
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from std_msgs.msg import Float32

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dunya as dunya_mod  # noqa: E402

V_MIN, V_MAX = 0.3, 1.5
VALIDATE = 2
BEST_EFFORT = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE,
                         history=HistoryPolicy.KEEP_LAST, depth=10)
RELIABLE = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.VOLATILE,
                      history=HistoryPolicy.KEEP_LAST, depth=10)
Z_DINLENME_VARSAYILAN = -0.013


def clamp(v, lo=V_MIN, hi=V_MAX):
    return min(hi, max(lo, v))


def multisine(seed):
    """0.9 + a sum of sines with a 20 s fundamental, peak deviation exactly
    0.6 m/s, so it never touches the [0.3, 1.5] limits. Schroeder phases keep
    the crest factor low for the amplitude available."""
    freqs = np.array([0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0])
    n = len(freqs)
    k = np.arange(1, n + 1)
    phases = -math.pi * k * (k - 1) / n + random.Random(seed).uniform(0, 2 * math.pi)
    t = np.linspace(0.0, 20.0, 4001)
    raw = np.sin(2 * math.pi * freqs[:, None] * t[None, :] + phases[:, None]).sum(axis=0)
    scale = 0.6 / np.abs(raw).max()
    return lambda tt: 0.9 + scale * float(np.sum(np.sin(2 * math.pi * freqs * tt + phases)))


def steps(seed, length=20.0):
    """0.3 / 1.5 alternating, dwell 1.5-3.5 s drawn from the seed."""
    rng = random.Random(seed + 7919)
    edges, t, level = [], 0.0, rng.choice((V_MIN, V_MAX))
    while t < length:
        edges.append((t, level))
        t += rng.uniform(1.5, 3.5)
        level = V_MAX if level == V_MIN else V_MIN
    return lambda tt: next(lv for t0, lv in reversed(edges) if tt >= t0)


def piecewise(seed, lo, hi):
    rng = random.Random(seed)
    pieces = []
    t = 0.0
    while t < 600.0:
        pieces.append((t, rng.uniform(lo, hi)))
        t += rng.uniform(0.5, 2.0)
    return lambda tt: next(v for t0, v in reversed(pieces) if tt >= t0)


class Politika(Node):
    def __init__(self, a):
        super().__init__('veri_politika')
        self.a = a
        self.dw = dunya_mod.Dunya(a.dunya_yaml)
        self.z_model = None
        self.z_rest = None
        self.landed = None
        self.h_ekf = None
        self.cand = None
        self.t_validate = None
        self.pub_v = self.create_publisher(Float32, '/eland/veri/v_ref', RELIABLE)
        self.pub_h = self.create_publisher(Float32, '/eland/veri/h_gercek_hedef', RELIABLE)
        self.create_subscription(LandingState, '/eland/state', self.on_state, RELIABLE)
        self.create_subscription(LandingCandidate, '/eland/candidate', self.on_cand, RELIABLE)
        self.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1',
                                 self.on_lp, BEST_EFFORT)
        self.create_subscription(VehicleLandDetected, '/fmu/out/vehicle_land_detected',
                                 self.on_land, BEST_EFFORT)
        self.gz = GzNode()
        self.gz.subscribe(Pose_V, f'/world/{a.gz_world}/dynamic_pose/info', self.on_gt)

        if a.kip == 'sabit':
            self.f = lambda t, ctx: clamp(a.hiz)
        elif a.kip == 'kahin':
            self.f = lambda t, ctx: clamp(a.d * ctx['h']) if ctx['h'] is not None else None
        elif a.kip == 'rastgele' and a.varyant == 'parca':
            g = piecewise(a.tohum, V_MIN, V_MAX)
            self.f = lambda t, ctx: clamp(g(t))
        elif a.kip == 'rastgele' and a.varyant == 'carpan':
            g = piecewise(a.tohum, 0.5, 1.5)
            self.f = lambda t, ctx: (clamp(self.law() * g(t))
                                     if self.law() is not None else None)
        elif a.kip == 'k4':
            first, second = multisine(a.tohum), steps(a.tohum)
            if a.tohum % 2:
                first, second = second, first
            self.f = lambda t, ctx: (first(t) if t < 20.0 else
                                     second(t - 20.0) if t < 40.0 else V_MIN)
        else:
            raise SystemExit(f'bilinmeyen kip {a.kip}')
        self.create_timer(0.02, self.tick)
        self.get_logger().info(f'politika: {vars(a)}')

    # ------------------------------------------------------------ inputs
    def on_gt(self, msg):
        for p in msg.pose:
            if p.name == self.a.model:
                self.z_model = (p.position.x, p.position.y, p.position.z)
                if self.z_rest is None and self.landed:
                    self.z_rest = p.position.z - self.dw.yuzey_z(p.position.x, p.position.y)
                break

    def on_land(self, msg):
        self.landed = bool(msg.landed)

    def on_lp(self, msg):
        self.h_ekf = -float(msg.z)

    def on_cand(self, msg):
        if msg.valid:
            self.cand = msg

    def on_state(self, msg):
        if msg.state == VALIDATE and self.t_validate is None:
            self.t_validate = self.get_clock().now().nanoseconds * 1e-9

    # ------------------------------------------------------------ helpers
    def h_hedef(self):
        if self.z_model is None:
            return None
        z_rest = self.z_rest if self.z_rest is not None else Z_DINLENME_VARSAYILAN
        return self.z_model[2] - self.dw.hedef_z() - z_rest

    def law(self):
        """The mode's descent law, recomputed (descentSpeed in the mode)."""
        if self.h_ekf is None:
            return None
        c = self.cand
        if c is None or c.area_m2 <= 0.0:
            return clamp(0.35 * self.h_ekf, V_MIN, V_MAX)
        ceiling = clamp(0.20 * math.sqrt(c.area_m2), V_MIN, V_MAX)
        if not c.view_bounded:
            return clamp(0.35 * self.h_ekf, V_MIN, ceiling)
        return clamp(ceiling * (1.0 - min(max(c.area_ratio, 0.0), 1.0)), V_MIN, ceiling)

    # ------------------------------------------------------------ output
    def tick(self):
        h = self.h_hedef()
        if h is not None and not self.a.devir_yok:
            self.pub_h.publish(Float32(data=float(h)))
        if self.t_validate is None:
            return
        t = self.get_clock().now().nanoseconds * 1e-9 - self.t_validate
        if self.a.devir_yok and h is not None and h < self.a.devir_irtifasi:
            v = self.a.son_hiz
        else:
            v = self.f(t, {'h': h})
        if v is not None:
            self.pub_v.publish(Float32(data=float(v)))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('kip', choices=['sabit', 'kahin', 'rastgele', 'k4'])
    p.add_argument('--hiz', type=float, default=1.0)
    p.add_argument('--d', type=float, default=0.35)
    p.add_argument('--varyant', choices=['parca', 'carpan'], default='parca')
    p.add_argument('--tohum', type=int, default=1)
    p.add_argument('--dunya-yaml', required=True)
    p.add_argument('--gz-world', required=True)
    p.add_argument('--model', default='x500_seg_cam_down_0')
    p.add_argument('--devir-yok', action='store_true')
    p.add_argument('--devir-irtifasi', type=float, default=2.5)
    p.add_argument('--son-hiz', type=float, default=0.5)
    a = p.parse_args()
    rclpy.init()
    node = Politika(a)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
