"""Extra observation channels (amendment 16), shared by the environment and the ROS node so that both build
exactly the same input. Ideas from de la Torre-Vanegas et al. 2025, "Vision-Based Risk Aware Emergency
Landing for UAVs in Complex Urban Environments" (arXiv 2505.20423):

  risk    graded risk of each pixel's class instead of the binary target mask (their risk map)
  hedef   the classic landing point as a hint: argmin over target pixels of smoothed risk + beta x distance
          to the image centre (their local-minimum detection), drawn as a small blob
  hafiza  risk memory: the highest risk ever seen at each ground cell since the episode began (their global
          risk map), shown as a heading-up map of a fixed 48 m square around the vehicle, so what was seen from
          high up is still there when the camera's view has narrowed near the ground

All three use only what the vehicle has: the class image, the camera pose and the altitude.
"""
import math

import cv2
import numpy as np

from .camera import HFOV

KANALLAR = ('risk', 'hedef', 'hafiza')
#: class -> risk, ordered as the 'zemin' rewards rank the harm (taxonomy index; 7 = unknown / off the photo)
RISK = np.array([0.0, 0.15, 0.5, 0.7, 0.8, 0.95, 1.0, 0.6], np.float32)
BILINMEYEN = 1.0          # never-seen ground in the memory map: treated as risky


def risk_kanali(sem):
    return RISK[sem]


def hedef_kanali(sem, hedef, irtifa_m, beta=0.5, sigma_m=1.5, blob_px=3.0, hfov=HFOV):
    """Blob at argmin over target pixels of (risk blurred over sigma_m) + beta x metric distance to the image
    centre / half the image width. The 128x128 image is 4:3 stretched: a row step is 0.75 of a column step on the
    ground. All zeros when no target pixel is in view."""
    if not hedef.any():
        return np.zeros(sem.shape, np.float32)
    n = sem.shape[1]
    px_m = 2.0 * max(irtifa_m, 0.1) * math.tan(hfov / 2) / n          # column step on the ground
    sx = max(sigma_m / px_m, 0.5)
    rs = cv2.GaussianBlur(RISK[sem], (0, 0), sigmaX=sx, sigmaY=max(sx / 0.75, 0.5), borderType=cv2.BORDER_REPLICATE)
    v, u = np.mgrid[0:sem.shape[0], 0:n].astype(np.float32)
    du, dv = u + 0.5 - n / 2, (v + 0.5 - sem.shape[0] / 2) * 0.75
    uzak = np.sqrt(du * du + dv * dv) / (n / 2)
    V = np.where(hedef, rs + beta * uzak, np.inf)
    i, j = np.unravel_index(int(np.argmin(V)), V.shape)
    g = np.exp(-((u - j) ** 2 + ((v - i) * 0.75) ** 2) / (2 * blob_px ** 2))
    return g.astype(np.float32)


class RiskHafizasi:
    """World-frame grid of the highest risk seen per cell (pixel-wise max, as their global risk map)."""

    def __init__(self, hucre_m=0.25, yari_m=90.0, gorus_m=48.0, boyut=128):
        self.h, self.yari, self.gorus_m, self.n = hucre_m, yari_m, gorus_m, boyut
        k = int(round(2 * yari_m / hucre_m))
        self.izgara = np.full((k, k), -1.0, np.float32)     # -1 = never seen
        self.merkez = np.zeros(2)

    def sifirla(self, x, y):
        self.izgara.fill(-1.0)
        self.merkez = np.array([x, y], float)

    def _hucre(self, X, Y):
        k = self.izgara.shape[0]
        sonlu = np.isfinite(X) & np.isfinite(Y)             # rays above the horizon never reach the ground
        X, Y = np.where(sonlu, X, self.merkez[0]), np.where(sonlu, Y, self.merkez[1])
        c = np.floor((X - self.merkez[0] + self.yari) / self.h).astype(np.int64)
        r = np.floor((self.merkez[1] + self.yari - Y) / self.h).astype(np.int64)
        return r, c, sonlu & (r >= 0) & (r < k) & (c >= 0) & (c < k)

    def guncelle(self, X, Y, risk, gecerli):
        r, c, ok = self._hucre(X, Y)
        ok &= gecerli
        np.maximum.at(self.izgara, (r[ok], c[ok]), risk[ok])

    def gorus(self, x, y, yaw):
        """Heading-up map: row 0 = ahead (nose), column 0 = the vehicle's left, as the camera image."""
        n, s = self.n, self.gorus_m / self.n
        # map pixel (col j, row i) -> body (bx ahead, by left) -> world -> grid (col, row)
        cy, sy = math.cos(yaw), math.sin(yaw)
        # body: bx = (n/2 - i - 0.5) s, by = (n/2 - j - 0.5) s ; world X = x + cy bx - sy by, Y = y + sy bx + cy by
        # grid col = (X - mx + yari)/h - 0.5 , row = (my + yari - Y)/h - 0.5  (cell centres)
        a = np.array([[sy * s, -cy * s], [cy * s, sy * s]]) / self.h        # d(col,row)/d(j,i)
        j0 = i0 = n / 2 - 0.5
        c0 = (x - self.merkez[0] + self.yari) / self.h - 0.5
        r0 = (self.merkez[1] + self.yari - y) / self.h - 0.5
        # (col,row) = (c0,r0) + a @ ([j,i] - [j0,i0]) ; cv2 wants dst->src as a 2x3 matrix
        M = np.hstack([a, (np.array([c0, r0]) - a @ np.array([j0, i0]))[:, None]]).astype(np.float64)
        out = cv2.warpAffine(self.izgara, M, (n, n), flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=-1.0)
        return np.where(out < 0, BILINMEYEN, out).astype(np.float32)


def ek_kanallar(kanallar, sem, hedef, irtifa_m, X, Y, gecerli, poz, yaw, hafiza):
    """The requested extra channels, in KANALLAR order. hafiza is updated here (call once per step)."""
    out = []
    for k in KANALLAR:
        if k not in kanallar:
            continue
        if k == 'risk':
            out.append(risk_kanali(sem))
        elif k == 'hedef':
            out.append(hedef_kanali(sem, hedef, irtifa_m))
        else:
            hafiza.guncelle(X, Y, RISK[sem], gecerli)
            out.append(hafiza.gorus(poz[0], poz[1], yaw))
    return out
