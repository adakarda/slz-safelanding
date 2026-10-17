"""PX4's closed-loop answer to a velocity command, in its simplest useful form.

The policy never touches motors: it asks PX4 for a velocity, and what comes
back is PX4's velocity loop, not a free rigid body. So this models that loop,
not the airframe (docs/onkayit/rl_f0_onkayit.md section 2.4, amendment 1):

  * the command takes effect after a pure delay (cmd_delay_xy / cmd_delay_z),
  * first-order velocity response, separate time constants for xy and z,
  * horizontal acceleration capped at a_max,
  * the body tilts with the horizontal acceleration, atan(a / g), plus a
    small constant trim tilt, and the camera tilts with it -- at 25 m an
    11.5 deg tilt moves the image centre about 5 m, twenty lateral steps,
  * the camera image is late by `latency_s` (segmentation time and transport).

DEFAULTS ARE MEASURED. Identification flight F1 (2026-10-16, x500_seg_cam_rgb_down,
offboard velocity setpoints, ~/rl_inis/tanilama/kos1): fitted over the whole
record, steps and 160 random policy-like actions,

    tau_xy 0.50 s, a_max 2.0 m/s^2, cmd_delay_xy 0.24 s   RMSE 0.056 m/s
    tau_z  0.15 s, cmd_delay_z 0.10 s                     RMSE 0.039 m/s (steps)
    tilt = 0.91 atan(a/g) + 0.69 deg (r 0.977); hover trim 0.9 deg

Without the delay the same record is fitted three times worse (0.206 m/s on
the random part), so the delay is the term that matters most.
"""
import collections
import math
from dataclasses import dataclass

import numpy as np

from .camera import rotation

G = 9.81


@dataclass
class DynamicsParams:
    tau_xy: float = 0.50       # s
    tau_z: float = 0.15        # s
    a_max: float = 2.0         # m/s^2
    cmd_delay_xy: float = 0.24  # s
    cmd_delay_z: float = 0.10  # s
    latency_s: float = 0.2     # s, perception (v3 140-270 ms measured, 2026-10-15)
    tilt_bias_deg: float = 0.9  # constant trim tilt, measured at hover
    tilt_bias_dir: float = 0.0  # rad, direction of the trim tilt in the world
    substep_s: float = 0.05    # s

    def randomised(self, rng, spread=None):
        """Per-episode draw (pre-registered + amendment 1):
        tau and command delays +-50 %, a_max +-30 %, latency 0..0.4 s,
        trim tilt 0..1.5 deg in a random direction."""
        s = spread or {'tau': 0.5, 'a_max': 0.3, 'latency': (0.0, 0.4), 'delay': 0.5, 'bias_deg': (0.0, 1.5)}
        u = lambda c, f: c * rng.uniform(1 - f, 1 + f)  # noqa: E731
        return DynamicsParams(
            tau_xy=u(self.tau_xy, s['tau']), tau_z=u(self.tau_z, s['tau']),
            a_max=u(self.a_max, s['a_max']),
            cmd_delay_xy=u(self.cmd_delay_xy, s['delay']), cmd_delay_z=u(self.cmd_delay_z, s['delay']),
            latency_s=rng.uniform(*s['latency']),
            tilt_bias_deg=rng.uniform(*s['bias_deg']), tilt_bias_dir=rng.uniform(0, 2 * math.pi),
            substep_s=self.substep_s)


class Vehicle:
    """Position, velocity and attitude of the camera; keeps short histories for the delays."""

    def __init__(self, params, pos, yaw):
        self.p = params
        self.pos = np.array(pos, float)
        self.vel = np.zeros(3)
        self.acc = np.zeros(3)
        self.yaw = float(yaw)
        self.t = 0.0
        b = G * math.tan(math.radians(params.tilt_bias_deg))
        self._bias = np.array([b * math.cos(params.tilt_bias_dir), b * math.sin(params.tilt_bias_dir)])
        self._cmds = collections.deque([(-1e9, np.zeros(3))])
        n = int(np.ceil(max(params.latency_s, 0.0) / params.substep_s)) + 2
        self.history = collections.deque(maxlen=n)
        self.history.append(self._record())

    def attitude(self):
        # thrust is m (a + g z): the body z axis points along it
        return rotation((self.acc[0] + self._bias[0], self.acc[1] + self._bias[1],
                         max(G + self.acc[2], 1.0)), self.yaw)

    def _active(self, delay, axis):
        """Command component(s) issued at least `delay` ago."""
        cut = self.t - delay + 1e-9
        v = self._cmds[0][1]
        for t, c in self._cmds:
            if t > cut:
                break
            v = c
        return v[axis]

    def _record(self):
        # the attitude is computed later, only for the record the camera actually uses (delayed_pose):
        # same rotation() on the same numbers, ~5x fewer calls
        return [self.t, self.pos.copy(), self.acc.copy(), self.yaw, None]

    def _rotation_of(self, rec):
        if rec[4] is None:
            a = rec[2]
            rec[4] = rotation((a[0] + self._bias[0], a[1] + self._bias[1], max(G + a[2], 1.0)), rec[3])
        return rec[4]

    def step(self, v_cmd, duration):
        """Command v_cmd (world frame) now, and fly for `duration` seconds."""
        self._cmds.append((self.t, np.asarray(v_cmd, float).copy()))
        keep = max(self.p.cmd_delay_xy, self.p.cmd_delay_z) + 1.0
        while len(self._cmds) > 2 and self._cmds[1][0] < self.t - keep:
            self._cmds.popleft()
        dt = self.p.substep_s
        for _ in range(max(1, int(round(duration / dt)))):
            cxy = self._active(self.p.cmd_delay_xy, slice(0, 2))
            cz = self._active(self.p.cmd_delay_z, 2)
            a = np.empty(3)
            a[:2] = (cxy - self.vel[:2]) / self.p.tau_xy
            a[2] = (cz - self.vel[2]) / self.p.tau_z
            n = math.hypot(a[0], a[1])
            if n > self.p.a_max:
                a[:2] *= self.p.a_max / n
            self.acc = a
            self.vel += a * dt
            self.pos += self.vel * dt
            self.t += dt
            self.history.append(self._record())

    def delayed_pose(self):
        """(position, rotation) as the camera image arriving now shows it."""
        target = self.t - self.p.latency_s
        for rec in self.history:             # oldest first; first one not too old wins
            if rec[0] >= target - 1e-9:
                return rec[1], self._rotation_of(rec)
        return self.history[-1][1], self._rotation_of(self.history[-1])
