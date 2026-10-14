"""Height above the landing surface, estimated while descending (pure, no ROS).

``yukseklik_gozlemci`` runs this live and ``tools/veri/gozlemci_cevrimdisi.py``
replays the same code over recorded episodes.

While the safe region under the image centre fits in view (``view_bounded``),
its pixel share is

    rho = A / (K h^2),          K = p_hesap.AYAK_IZI = 4.216

with h the camera's height above the region's surface and A its area. In logs

    ln rho = c - 2x,            x = ln h,   c = ln(A / K).

One frame gives only c - 2x. What separates x from c is motion: h' = -vz, so
x' = -vz/h, and a wrong x makes the predicted ln rho drift away from the
measured one at a rate set by the divergence D = vz/h. Hovering (vz = 0)
carries no information at all.

Outside ``view_bounded`` the relation does not hold: measured on 62 episodes,
a region running off the frame edge reads 10-29% below A/(K h^2) while
rho < 0.75. Those frames are gated out, never fitted.

Three estimators share one interface:

``Sabit``   the fixed-gain observer (owner's design, 2026-10-14)

                nu  = ln rho - (c^ - 2 x^)
                x^' = -vz exp(-x^) - Kx nu
                c^' = Kc nu

            Linearised, the error e = (x^ - x, c^ - c) obeys
            e' = [[D - 2Kx, Kx], [2Kc, -Kc]] e: trace D - 2Kx - Kc,
            determinant -Kc D. Stable iff Kc < 0 and 2Kx + Kc > D.

``Kalman``  the same model, the gain taken from a 2x2 covariance: large while
            little is known, shrinking as frames arrive.

``Dogrudan`` the baseline: each usable frame replaces x^ by (c0 - ln rho)/2
            with c0 from the map's area, frozen. No filtering.

A frame is compared with x^ as it was at the frame's capture stamp (a short
history), and the correction is added to the current state. Ignoring the stamp
cost 2.4x the error with 0.2 s of delay in the offline replay (W3).

Starting values come from the EKF height and the map's area_m2. Both carry
the same error over raised ground: mapping_node projects onto z = 0 of the
EKF frame with the EKF height, so area_m2 grows with h_ekf^2 and c0 - 2 x0
cancels it. nu0 ~ 0 by construction (measured: see `gozlemci_cevrimdisi.py
nu0`), so only the descent itself can tell the two apart. After the first
frame every new piece of information comes from the descent (the error
dynamics' determinant is -Kc D): hovering, nothing is learnt.

Anything that breaks that tie needs this rechecked, because with
|nu0| > nu_max the outlier gate rejects every frame and the estimate never
moves:
- h^ fed into the mapping;
- a downward rangefinder (``dist_bottom_valid``): mapping_node then projects
  with dist_bottom, so area_m2 moves towards the true area -- anywhere
  between A and (h_ekf/h)^2 A, depending on how much of the region was mapped
  from above it -- while x0 taken from the EKF keeps its error, since the EKF
  still refers height to the take-off point (EKF2_HGT_REF = GNSS; with that
  reference PX4 only resets its terrain state to the range). On W5 that puts
  nu0 = 2 ln(h_ekf/h) - ln(A0/A) between ~0 and ~0.6 (computed, not run). With
  a rangefinder, start x0 from dist_bottom and c0 from the first frame.

Depends on ``p_hesap.py`` (same package, from the p-kestirici work, v7.0) for
AYAK_IZI, so the batch estimator p_kestirici and this observer cannot disagree
on the camera geometry. This module does not import without it.
"""

import math
from collections import deque

from eland_mapping.p_hesap import AYAK_IZI

#: Gate bits: why a frame did not correct the estimate.
KAPI_RHO_YOK = 1      # rho <= 0: nothing landable under the centre, no log
KAPI_DOYUM = 2        # rho >= rho_doyum: the region fills the view
KAPI_SINIR = 4        # region touches the frame edge: the model does not hold
KAPI_EGIKLIK = 8      # body tilt above the limit
KAPI_AYKIRI = 16      # |nu| above nu_max: an outlier frame

X_ALT = math.log(0.1)
X_UST = math.log(50.0)


def kazanc_gecerli(kx, kc, alt=0.5):
    """Accept fixed gains only inside the stable region, with margin.

    2Kx + Kc must exceed D = vz/h for stability; ``alt`` is the margin. The
    descent law's own D is 0.35 at most (v = 0.35 h).
    Returns (ok, reason).
    """
    if kc >= 0.0:
        return False, 'Kc >= 0: determinant -Kc*D <= 0, kararsiz'
    if kx <= 0.0:
        return False, 'Kx <= 0'
    if 2.0 * kx + kc < alt:
        return False, f'2Kx + Kc = {2.0 * kx + kc:.2f} < {alt:.2f}: D bunu asinca kararsiz'
    return True, ''


class Kapilar:
    """Which frames may correct the estimate."""

    def __init__(self, rho_doyum=0.75, nu_max=0.5, sinirli=True, egiklik_deg=5.0):
        self.rho_doyum = rho_doyum
        self.nu_max = nu_max            # None: off
        self.sinirli = sinirli          # gate frames whose region touches the edge
        self.egiklik_deg = egiklik_deg  # None: off

    def on_kapi(self, rho, view_bounded, egiklik):
        """Gates decided before nu exists. 0 = the frame may be used."""
        if not (rho > 0.0):
            return KAPI_RHO_YOK
        if rho >= self.rho_doyum:
            return KAPI_DOYUM
        if self.sinirli and not view_bounded:
            return KAPI_SINIR
        if self.egiklik_deg is not None and egiklik is not None and egiklik > self.egiklik_deg:
            return KAPI_EGIKLIK
        return 0

    def aykiri(self, nu):
        return self.nu_max is not None and abs(nu) > self.nu_max


class _Taban:
    """State, propagation and the capture-stamp history shared by both."""

    def __init__(self, kapilar=None, gecmis_s=1.5):
        self.kapilar = kapilar or Kapilar()
        self.gecmis_s = gecmis_s
        self.x = None
        self.c = None
        self.t = None
        self.nu = 0.0
        self.son_kapi = 0
        self.kullanilan = 0
        self.kapi_sayac = {KAPI_RHO_YOK: 0, KAPI_DOYUM: 0, KAPI_SINIR: 0,
                           KAPI_EGIKLIK: 0, KAPI_AYKIRI: 0}
        self._gecmis = deque()
        self._t_son_olcum = None

    @property
    def hazir(self):
        return self.x is not None

    @property
    def h(self):
        """Camera height above the surface, m."""
        return math.exp(self.x)

    @property
    def alan(self):
        return AYAK_IZI * math.exp(self.c)

    def baslat(self, t, h0, alan0):
        """h0: camera height guess (EKF + camera offset); alan0: the map's area."""
        self.x = min(max(math.log(max(h0, 0.1)), X_ALT), X_UST)
        self.c = math.log(max(alan0, 1e-3) / AYAK_IZI)
        self.t = t
        self.nu = 0.0
        self.son_kapi = 0
        self.kullanilan = 0
        for k in self.kapi_sayac:
            self.kapi_sayac[k] = 0
        self._gecmis.clear()
        self._gecmis.append((t, self.x))
        self._t_son_olcum = None
        self._baslat_ek()

    def _baslat_ek(self):
        pass

    def ilerlet(self, t, vz):
        """Propagate to time t with the downward speed vz (m/s, down +)."""
        if self.x is None or t <= self.t:
            return
        dt = t - self.t
        d = vz * math.exp(-self.x)        # divergence vz/h on the estimate
        self.x = min(max(self.x - d * dt, X_ALT), X_UST)
        self._ilerlet_ek(d, dt)
        self.t = t
        self._gecmis.append((t, self.x))
        while self._gecmis and self._gecmis[0][0] < t - self.gecmis_s:
            self._gecmis.popleft()

    def _ilerlet_ek(self, d, dt):
        pass

    def x_zamaninda(self, t):
        """x^ as it was at time t (nearest recorded step, not after t)."""
        best = None
        for tt, xx in self._gecmis:
            if tt <= t:
                best = xx
            else:
                break
        return best if best is not None else (self._gecmis[0][1] if self._gecmis else self.x)

    def olcum(self, t_yakalama, rho, view_bounded, egiklik=None, damga_kullan=True):
        """One frame. Returns the gate bits (0 = used)."""
        if self.x is None:
            return KAPI_RHO_YOK
        kapi = self.kapilar.on_kapi(rho, view_bounded, egiklik)
        if kapi:
            self.kapi_sayac[kapi] += 1
            self.son_kapi = kapi
            self.nu = 0.0
            return kapi
        xp = self.x_zamaninda(t_yakalama) if damga_kullan else self.x
        nu = math.log(rho) - (self.c - 2.0 * xp)
        if self.kapilar.aykiri(nu):
            self.kapi_sayac[KAPI_AYKIRI] += 1
            self.son_kapi = KAPI_AYKIRI
            self.nu = nu
            return KAPI_AYKIRI
        # The fixed-gain observer is continuous; between frames nu is held,
        # so a frame weighs as much as the time since the previous one.
        dt_olcum = 0.1 if self._t_son_olcum is None else min(max(t_yakalama - self._t_son_olcum, 0.0), 0.2)
        self._t_son_olcum = t_yakalama
        self._duzelt(nu, dt_olcum)
        self.x = min(max(self.x, X_ALT), X_UST)
        self.nu = nu
        self.son_kapi = 0
        self.kullanilan += 1
        return 0

    def _duzelt(self, nu, dt_olcum):
        raise NotImplementedError


class Sabit(_Taban):
    """Fixed gains Kx, Kc; see the module docstring for the stability rule."""

    def __init__(self, kx=2.0, kc=-2.0, **kw):
        super().__init__(**kw)
        self.kx, self.kc = kx, kc

    def _duzelt(self, nu, dt_olcum):
        self.x += -self.kx * nu * dt_olcum
        self.c += self.kc * nu * dt_olcum


class Kalman(_Taban):
    """Extended Kalman filter on (x, c) with y = ln rho = c - 2x.

    sigma_olcum: 1-sigma noise of ln rho per frame; sigma_x0, sigma_c0: the
    initial uncertainty of x^ and c^; q_x, q_c: process noise per second.
    Plain floats: a 2x2 in numpy costs more than the arithmetic.
    """

    def __init__(self, sigma_olcum=0.02, sigma_x0=0.5, sigma_c0=0.7, q_x=1e-4, q_c=1e-5, **kw):
        super().__init__(**kw)
        self.r = sigma_olcum ** 2
        self.sx0, self.sc0 = sigma_x0, sigma_c0
        self.q_x, self.q_c = q_x, q_c
        self._baslat_ek()

    def _baslat_ek(self):
        self.pxx = self.sx0 ** 2
        self.pcc = self.sc0 ** 2
        self.pxc = 0.0

    def _ilerlet_ek(self, d, dt):
        # dx'/dx = vz exp(-x) = d, so F = [[1 + d dt, 0], [0, 1]]
        f = 1.0 + d * dt
        self.pxx = f * f * self.pxx + self.q_x * dt
        self.pxc = f * self.pxc
        self.pcc = self.pcc + self.q_c * dt

    def _duzelt(self, nu, dt_olcum):
        # H = [-2, 1]
        hx = -2.0 * self.pxx + self.pxc      # P H^T, x row
        hc = -2.0 * self.pxc + self.pcc      # P H^T, c row
        s = -2.0 * hx + hc + self.r
        kx, kc = hx / s, hc / s
        self.x += kx * nu
        self.c += kc * nu
        # P = (I - K H) P
        pxx = self.pxx - kx * hx
        pxc = self.pxc - kx * hc
        pcc = self.pcc - kc * hc
        self.pxx, self.pxc, self.pcc = pxx, pxc, pcc

    @property
    def sigma_h(self):
        """1-sigma of h^, m (first order)."""
        return self.h * math.sqrt(max(self.pxx, 0.0))


class Dogrudan(_Taban):
    """The baseline: height from one frame and a frozen area, no filtering.

        h = sqrt(A0 / (K rho)),    i.e.  x = (c0 - ln rho) / 2

    c0 = ln(A0 / K) from the candidate's area_m2 at VALIDATE entry and never
    corrected. Between usable frames, and once the region fills the view, it
    carries on with the descent like the observers. Same gates, except |nu|:
    there is no model to call a frame an outlier against.

    Over a raised target A0 comes from the map, which is projected with the
    EKF height (area_m2 grows with h_ekf^2), so this hands back roughly the
    EKF's own error. It is here to show that, not to land on.
    """

    def olcum(self, t_yakalama, rho, view_bounded, egiklik=None, damga_kullan=True):
        if self.x is None:
            return KAPI_RHO_YOK
        kapi = self.kapilar.on_kapi(rho, view_bounded, egiklik)
        if kapi:
            self.kapi_sayac[kapi] += 1
            self.son_kapi = kapi
            self.nu = 0.0
            return kapi
        xp = self.x_zamaninda(t_yakalama) if damga_kullan else self.x
        self.nu = math.log(rho) - (self.c - 2.0 * xp)
        # The frame measured the height at capture; the descent since then
        # (x now minus x then) carries it to the present.
        self.x = min(max(0.5 * (self.c - math.log(rho)) + (self.x - xp), X_ALT), X_UST)
        self.son_kapi = 0
        self.kullanilan += 1
        return 0
