"""Target-locking shield ("kilitli kalkan", amendment 22): the SORA shield, but it commits to one ground target.

Amendment 21's diagnosis: the remaining time-outs end 5-10 m up, 0.6-3 m from safe ground, zig-zagging. Below
below_m the shield turns every descent over an unsafe centre into a slide towards the NEAREST safe pixel, chosen
again every 0.25 s; that pixel sits on the edge of the safe area and swaps sides as the vehicle moves (command
delay 0.24 s), so the vehicle never gets its centre over it.

This shield, when it first has to stop a descent below below_m:
  - picks a target pixel inside the safe area, not on its edge: among the pixels at least min(pay_m + half the
    centre block, the deepest point of the area) from the edge, the one nearest the image centre,
  - turns it into a ground point with the camera pose (the same ray-plane projection the camera uses),
  - flies there, holding the heading, and overrides the policy until the vehicle is within varis_m of it,
  - then descends while the centre is safe; if the centre is not safe there, or the lock is older than omur_s,
    it lets go and picks again at the next stopped descent.
Nothing safe in view: hold, as the old shield does. Uses only what the vehicle has: the observation, its pose
estimate and the camera model.
"""
import math

import cv2
import numpy as np

from .camera import HFOV, ground_hits
from .pilots import centre_safe


class KilitliKalkan:
    def __init__(self, below_m=10.0, pay_m=0.5, varis_m=0.4, omur_s=8.0):
        self.below, self.pay, self.varis, self.omur = below_m, pay_m, varis_m, omur_s
        self.sifirla()

    def sifirla(self):
        self.hedef, self.t0 = None, 0.0

    def hedef_sec(self, obs, h, rays, kam_pos, R):
        """Ground (x, y) of the chosen target pixel, or None when nothing safe is in view."""
        g = (obs[2] > 0.5).astype(np.uint8)
        if not g.any():
            return None
        n = obs.shape[2]
        px_m = 2.0 * max(h, 0.1) * math.tan(HFOV / 2) / n          # column step on the ground
        derin = cv2.distanceTransform(g, cv2.DIST_L2, 3)            # pixels to the edge of the safe area
        esik = min(self.pay / px_m + 2.0, float(derin.max()))       # margin + half the 4x4 centre block
        ys, xs = np.nonzero(derin >= esik - 1e-6)
        d = np.hypot(xs + 0.5 - n / 2, (ys + 0.5 - obs.shape[1] / 2) * 0.75)
        j = int(np.argmin(d))
        X, Y, _ = ground_hits(rays, kam_pos, R)
        x, y = float(X[ys[j], xs[j]]), float(Y[ys[j], xs[j]])
        return (x, y) if math.isfinite(x) and math.isfinite(y) else None

    def __call__(self, action, obs, h, t, kam_pos, R, arac_xy, yaw, rays):
        """(action, overridden). kam_pos, R: the pose the observation was taken from; arac_xy: the vehicle's
        position now (both from the vehicle's own estimate); yaw: heading (rad), held through the episode."""
        if h >= self.below:
            self.sifirla()
            return action, False
        if self.hedef is not None and t - self.t0 > self.omur:
            self.sifirla()
        if self.hedef is None:
            if not ((action == 9 or action >= 10) and not centre_safe(obs)):
                return action, False                        # the old shield would not act either
            self.hedef = self.hedef_sec(obs, h, rays, kam_pos, R)
            self.t0 = t
            if self.hedef is None:
                return 0, True                              # nothing safe in view: hold
        dx, dy = self.hedef[0] - arac_xy[0], self.hedef[1] - arac_xy[1]
        if math.hypot(dx, dy) <= self.varis:
            if centre_safe(obs):
                return 9, action != 9
            self.sifirla()                                  # there, but not safe: let go, pick again later
            return 0, True
        rel = (math.degrees(math.atan2(dy, dx)) - math.degrees(yaw)) % 360.0
        a = 1 + int(round(rel / 45.0)) % 8
        return a, a != action
