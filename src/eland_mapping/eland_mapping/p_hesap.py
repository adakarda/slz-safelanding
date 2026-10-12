"""Target surface height and region area from the growth of the safe region.

Pure numpy, no ROS: ``p_kestirici`` uses it live and
``tools/veri/p_kestirimi.py`` runs the same arithmetic over recorded episodes.

While the safe region under the image centre fits in view, its pixel share is

    rho = A / (4.216 * d^2)        d: camera to the region's surface, A: its area

(4.216 = footprint area / h^2 of the 99.7 deg, 4:3 camera, checked against
Gazebo to RMS 0.002 below 5 deg of tilt). The EKF height is measured from the
take-off point, not from the surface, but it moves exactly as d does. With
d = h_ekf - P that is a straight line

    1 / sqrt(rho) = k * (h_ekf - P),        k = sqrt(4.216 / A)

so a line through the points (h_ekf, 1/sqrt(rho)) gives the surface height P
where it crosses zero and the area A from its slope. Only the EKF's
displacement is used, never its absolute height -- and not the map's area
either, which is projected with that same absolute height and so would just
hand it back (sqrt(A_map / (4.216 rho)) = h_ekf).

P is the surface height in the EKF's frame, offsets included: on flat ground
it comes out near the camera's mounting height below the EKF origin rather
than exactly 0, and h_ekf - P is the camera's distance to the surface.
"""

import math

import numpy as np

#: Footprint area over height squared for the 99.7 deg, 4:3 downward camera.
AYAK_IZI = 4.216


def _uydur(h, y):
    """Least squares y = a*h + b. Returns (a, b, cov, residuals) or None."""
    n = len(h)
    if n < 3:
        return None
    x = np.column_stack([h, np.ones(n)])
    xtx = x.T @ x
    if abs(np.linalg.det(xtx)) < 1e-12:
        return None
    beta = np.linalg.solve(xtx, x.T @ y)
    r = y - x @ beta
    s2 = float(r @ r) / max(n - 2, 1)
    return float(beta[0]), float(beta[1]), s2 * np.linalg.inv(xtx), r


def kestir(h_ekf, rho, kirpma=3.0):
    """Fit the line, drop frames off it by more than ``kirpma`` MADs, refit.

    Returns a dict -- p (surface height in the EKF frame, m), p_sigma (1 sigma
    from the fit), alan (m^2), artik_rms (residual RMS in 1/sqrt(rho) units),
    kullanilan (frames kept), egim (k) -- or None when there is nothing to fit.
    p is NaN when the line does not fall with height, which is what a region
    that is not the same surface throughout looks like.
    """
    h = np.asarray(h_ekf, dtype=float)
    r = np.asarray(rho, dtype=float)
    ok = np.isfinite(h) & np.isfinite(r) & (r > 0)
    h, y = h[ok], 1.0 / np.sqrt(r[ok])
    f = _uydur(h, y)
    if f is None:
        return None
    a, b, cov, res = f
    kept = len(h)
    dev = np.abs(res - np.median(res))
    mad = 1.4826 * float(np.median(dev))
    if mad > 0:
        keep = dev <= kirpma * mad
        if 3 <= keep.sum() < len(h):
            f2 = _uydur(h[keep], y[keep])
            if f2 is not None:
                a, b, cov, res = f2
                kept = int(keep.sum())
    out = dict(kullanilan=kept, egim=a,
               artik_rms=float(math.sqrt(float(np.mean(res * res)))),
               p=float('nan'), p_sigma=float('nan'), alan=float('nan'))
    if a <= 0:
        return out
    p = -b / a
    # p = -b/a, first order: var p = (var b + p^2 var a + 2 p cov ab) / a^2
    var = (cov[1, 1] + p * p * cov[0, 0] + 2.0 * p * cov[0, 1]) / (a * a)
    out.update(p=float(p), p_sigma=float(math.sqrt(max(var, 0.0))),
               alan=float(AYAK_IZI / (a * a)))
    return out


def iraksama(t, rho):
    """Divergence D = (d ln rho / dt) / 2, slope over the given frames, 1/s.

    rho / rho = 2 v / d for a region that fits in view, so this is v/d -- the
    inverse of the time to contact -- with no height at all. NaN with fewer
    than three frames or no time spread.
    """
    t = np.asarray(t, dtype=float)
    r = np.asarray(rho, dtype=float)
    ok = np.isfinite(t) & np.isfinite(r) & (r > 0)
    t, lr = t[ok], np.log(r[ok])
    if len(t) < 3 or np.ptp(t) <= 0:
        return float('nan')
    a = np.polyfit(t - t[0], lr, 1)[0]
    return float(a / 2.0)


def egiklik_deg(qw, qx, qy, qz):
    """Angle between the body's down axis and true down, from a PX4 quaternion."""
    c = 1.0 - 2.0 * (qx * qx + qy * qy)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))
