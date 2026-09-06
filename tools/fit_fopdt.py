#!/usr/bin/env python3
"""Identify the vertical channel and derive PI gains from the model.

Records the commanded and achieved vertical speed while the mode runs its
square-wave identification, fits a first-order-plus-dead-time model to each
half period, and applies the IMC tuning rule for a PI controller.

Model, per step:

    v(t) = v0 + K (v_step - v0) (1 - exp(-(t - theta) / tau))   for t >= theta

  K      steady-state gain, dimensionless: 1.0 would mean the plant reaches
         exactly what it was asked for
  tau    time constant
  theta  dead time (setpoint transport over uXRCE-DDS plus the controller's
         own reaction)

IMC tuning for PI on a FOPDT plant, with lambda the desired closed-loop time
constant:

    Kc = tau / (K (lambda + theta))     Ti = tau     Ki = Kc / Ti

lambda is the one free choice left, and it is a stated trade-off rather than a
number pulled from the air: small lambda is fast and sensitive to the model
being wrong, large lambda is sluggish. The usual robust rule is
lambda >= max(0.5 tau, 1.5 theta), and that is what this prints.

Note the loop here also has a feedforward term equal to the reference, so the
PI only has to remove the residual: the derived Kc is an upper bound on what
is needed, not a requirement.
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


class Recorder(Node):
    def __init__(self, duration):
        super().__init__('fopdt_recorder')
        self.duration = duration
        self.t0 = time.time()
        self.vz = 0.0
        self.cmd = 0.0
        self.rows = []
        self.create_subscription(VehicleLocalPosition,
                                 '/fmu/out/vehicle_local_position_v1',
                                 self.on_pos, PX4_QOS)
        self.create_subscription(LandingState, '/eland/state', self.on_state,
                                 DECISION_QOS)
        self.create_timer(0.5, self.tick)

    def on_pos(self, msg):
        # Sample here, not on the state channel. The state channel is for
        # humans and runs an order of magnitude slower than the velocity
        # estimate; a first attempt sampled there and "identified" a 70 ms
        # time constant from 100 ms samples, which is arithmetic, not
        # measurement. The command changes only at the square wave's edges,
        # so holding the last one between them loses nothing.
        self.vz = float(msg.vz)
        self.rows.append((time.time() - self.t0, self.cmd, self.vz))

    def on_state(self, msg):
        self.cmd = float(msg.commanded_descent_mps)

    def tick(self):
        if time.time() - self.t0 > self.duration:
            raise SystemExit(0)


def slew_rate(t, y):
    """Fastest sustained rate of change in this step, in m/s^2.

    Reported separately from the model because the first identification run
    showed the model was the wrong shape: a +-1 m/s square wave asks for a
    2 m/s change, the vehicle answers with a straight ramp, and an
    exponential fitted to a ramp degenerates -- dead time 0.92 s, time
    constant pinned at the grid floor. A ramp is an acceleration limit, and an
    acceleration limit is not a time constant.
    """
    if len(t) < 6:
        return 0.0
    dv = np.diff(y) / np.maximum(np.diff(t), 1e-6)
    # Median of the fastest tenth: robust against single-sample spikes in the
    # velocity estimate while still describing the sustained slope.
    k = max(1, len(dv) // 10)
    return float(np.median(np.sort(np.abs(dv))[-k:]))


def fit_step(t, u, y):
    """One half period: grid search over dead time, least squares on the rest.

    Dead time enters the model non-linearly, and with 30-40 samples per step a
    grid over it is both faster and more robust than a general optimiser that
    can walk into a local minimum and report a confident wrong answer.
    """
    v0, v_step = y[0], u[-1]
    span = v_step - v0
    if abs(span) < 0.3 or len(t) < 8:
        return None
    best = None
    for theta in np.arange(0.0, min(1.5, 0.4 * (t[-1] - t[0])), 0.02):
        m = t >= t[0] + theta
        if m.sum() < 6:
            continue
        tt = t[m] - t[0] - theta
        for tau in np.arange(0.01, 3.0, 0.01):
            pred = v0 + span * (1.0 - np.exp(-tt / tau))
            res = float(np.mean((y[m] - pred) ** 2))
            if best is None or res < best[0]:
                best = (res, theta, tau)
    if best is None:
        return None
    _, theta, tau = best
    settled = y[t >= t[0] + min(theta + 3 * tau, t[-1] - t[0])]
    if settled.size == 0:
        return None
    k = float((settled.mean() - v0) / span)
    rate = slew_rate(t, y)
    # How long the acceleration limit alone would need for this step. When
    # that is not small next to the fitted time constant, the step never
    # entered the linear regime and the fit describes the limit, not the
    # plant.
    ramp_s = abs(span) / rate if rate > 1e-6 else float('inf')
    return {'K': k, 'tau': float(tau), 'theta': float(theta),
            'rms': float(np.sqrt(best[0])), 'slew': rate, 'ramp_s': ramp_s,
            'span': abs(float(span))}


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
    rclpy.init()
    node = Recorder(duration)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        rows = node.rows
        node.destroy_node()
        rclpy.try_shutdown()

    if len(rows) < 20:
        print('yeterli ornek yok')
        return 1
    t = np.array([r[0] for r in rows])
    u = np.array([r[1] for r in rows])
    y = np.array([r[2] for r in rows])

    # Split at every commanded step.
    edges = [0] + [i for i in range(1, len(u)) if abs(u[i] - u[i - 1]) > 0.2]
    fits = []
    for a, b in zip(edges, edges[1:] + [len(u)]):
        seg = slice(a, b)
        if b - a < 8:
            continue
        f = fit_step(t[seg], u[seg], y[seg])
        if f:
            fits.append(f)

    if not fits:
        print('basamak bulunamadi')
        return 1
    K = float(np.median([f['K'] for f in fits]))
    tau = float(np.median([f['tau'] for f in fits]))
    theta = float(np.median([f['theta'] for f in fits]))
    rate = len(t) / max(t[-1] - t[0], 1e-6)
    print(f'ornekleme hizi     : {rate:.1f} Hz ({len(t)} ornek)')
    print(f'basamak sayisi     : {len(fits)}')
    print(f'kazanc K           : {K:.3f}  '
          f'(dagilim {min(f["K"] for f in fits):.2f}-{max(f["K"] for f in fits):.2f})')
    print(f'zaman sabiti tau   : {tau:.3f} s  '
          f'(dagilim {min(f["tau"] for f in fits):.2f}-{max(f["tau"] for f in fits):.2f})')
    print(f'olu zaman theta    : {theta:.3f} s')
    print(f'uyum RMS           : {float(np.median([f["rms"] for f in fits])):.3f} m/s')
    slew = float(np.median([f['slew'] for f in fits]))
    ramp = float(np.median([f['ramp_s'] for f in fits]))
    span = float(np.median([f['span'] for f in fits]))
    print(f'egim (ivme) siniri : {slew:.2f} m/s2, {span:.2f} m/s basamak '
          f'icin {ramp:.2f} s rampa')
    if ramp > tau:
        # Delay-dominant case. The transient is shaped by the planner's jerk
        # and acceleration limits, so there is no exponential to read a time
        # constant off: tau sits at the search floor at every amplitude tried,
        # and the measured slope even falls with amplitude (4.94 m/s2 for a
        # 1.9 m/s step, 1.67 for a 0.55 m/s one), which is jerk limiting, not
        # a first-order lag.
        #
        # IMC for a plant that is gain plus delay (tau -> 0) collapses to an
        # almost pure integrator:
        #
        #     Ki = 1 / (K (lambda + theta))     Kp -> 0
        #
        # and Kp -> 0 is the right answer here rather than a degenerate one:
        # the loop already feeds the reference forward, so with K ~ 1 the
        # proportional term has nothing left to supply in steady state.
        print('  NOT: gecici rejim ivme/jerk siniriyla sekilleniyor, ustel '
              'degil. Zaman sabiti okunamaz; olu zaman baskin duruma gore '
              'turetiliyor.')
        for name, lam in (('lambda = 1.5 theta (dayanikli)', 1.5 * theta),
                          ('lambda = theta (agresif)', theta)):
            ki = 1.0 / (K * (lam + theta))
            print(f'{name}: lambda {lam:.2f} s -> Kp 0.00, Ki {ki:.2f} 1/s')
        return 0

    lam = max(0.5 * tau, 1.5 * theta)
    for name, l in (('lambda = max(0.5 tau, 1.5 theta)', lam),
                    ('lambda = tau (daha yumusak)', tau)):
        kc = tau / (K * (l + theta))
        ti = tau
        print(f'{name}: lambda {l:.2f} s -> Kp {kc:.2f}, Ti {ti:.2f} s, '
              f'Ki {kc / ti:.2f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
