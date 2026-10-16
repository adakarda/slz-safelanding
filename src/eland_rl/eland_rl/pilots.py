"""Hand-written pilots and the SORA shield, all working only from what the vehicle has:
the 3-channel observation (classes, depth, SORA channel) and its height.

The 128x128 image is stretched from 4:3, so a row step is 0.75 of a column step on
the ground; image up is the nose, actions count counter-clockwise from it.
"""
import math

import numpy as np

CENTRE = slice(62, 66)


def centre_safe(obs):
    return bool((obs[2, CENTRE, CENTRE] > 0.5).all())


def towards_nearest_safe(obs):
    """Lateral action (1..8) towards the nearest SORA-safe pixel, or 0 (hold) if none is visible."""
    ys, xs = np.nonzero(obs[2] > 0.5)
    if not len(ys):
        return 0
    dx, dy = xs - 64 + 0.5, (ys - 64 + 0.5) * 0.75
    j = int(np.argmin(dx * dx + dy * dy))
    ang = math.degrees(math.atan2(-dx[j], -dy[j])) % 360.0
    return 1 + int(round(ang / 45.0)) % 8


def channel_pilot(obs):
    """Descend over SORA-safe ground, else slide to the nearest safe pixel, else descend."""
    if centre_safe(obs):
        return 9
    a = towards_nearest_safe(obs)
    return 9 if a == 0 else a


def shield(action, obs, height_m, below_m=10.0):
    """SORA shield (amendment 5 analysis): below below_m a descend over a centre the SORA channel
    does not call safe becomes a slide towards the nearest safe pixel (or a hold). Returns
    (action, overridden)."""
    if action == 9 and height_m < below_m and not centre_safe(obs):
        return towards_nearest_safe(obs), True
    return action, False
