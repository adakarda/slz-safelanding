"""A flat scene: one nadir photo's class mask laid on the ground at true size.

This is scene type S1 of docs/onkayit/rl_f0_onkayit.md. The Gazebo worlds
built from the same photos (e.g. orto_dji0097) put the photo on a plane
centred on the world origin, and this class uses exactly that convention, so a
pose in Gazebo and a pose here look at the same ground:

    u (photo column) grows towards +x (east),
    v (photo row)    grows towards -y (south),
    fu = X / size_x + 0.5,   fv = 0.5 - Y / size_y

Masks are stored as taxonomy indices 0..6 (eland_common.classes); anything
that is not on the photo, or that the photo's annotator left void, is UNKNOWN.
"""
import re

import cv2
import numpy as np

from eland_common import classes

#: MESSI index -> taxonomy index, as v3 was trained (offline test, 2026-10-15).
#: 0 (void) is left out and becomes UNKNOWN.
MESSI_TO_TAXONOMY = {1: 5, 2: 3, 3: 3, 4: 3, 5: 6, 6: 3, 7: 0, 8: 3, 9: 0, 10: 3,
                     11: 2, 12: 2, 13: 5, 14: 1, 15: 4}

#: Classes the SORA separation is owed to (eland_common.classes).
HAZARD = np.array(classes.DEFAULT_HAZARD_CLASSES)


def lookup_table(mapping):
    """256-entry table: source index -> taxonomy index, UNKNOWN where unmapped."""
    lut = np.full(256, classes.UNKNOWN, np.uint8)
    for k, v in mapping.items():
        lut[k] = v
    return lut


def dji_ground_size(jpg_path, sensor_width_mm=13.2):
    """(size_x, size_y) in metres of a nadir DJI photo, from its own metadata.

    Altitude is the XMP RelativeAltitude (take-off relative, so flat ground
    is assumed); focal length is EXIF FocalLength. GSD = H * sensor / (f * W).
    """
    from PIL import Image
    raw = open(jpg_path, 'rb').read(400000)
    m = re.search(rb'drone-dji:RelativeAltitude="([^"]+)"', raw) or \
        re.search(rb'<drone-dji:RelativeAltitude>([^<]+)<', raw)
    if not m:
        raise ValueError(f'{jpg_path}: no RelativeAltitude in XMP')
    altitude = float(m.group(1))
    im = Image.open(jpg_path)
    focal = float(im.getexif().get_ifd(0x8769)[0x920A])
    w, h = im.size
    gsd = altitude * sensor_width_mm / (focal * w)
    return w * gsd, h * gsd


class Scene:
    """Class mask on the ground, plus what the reward and the metrics need."""

    def __init__(self, mask, size_m, photo=None, name='', dist_cell_m=0.1):
        """mask: HxW uint8 taxonomy indices; size_m: (size_x, size_y) metres."""
        self.mask = np.ascontiguousarray(mask, np.uint8)
        self.size = (float(size_m[0]), float(size_m[1]))
        self.photo = photo
        self.name = name
        self.pred = None     # optional v3 prediction mask, same shape as mask (amendment 7)
        self.elev = None     # optional Depth Anything relative elevation, uint8, same shape
        self.dist_cell = dist_cell_m
        self._dist = None

    @property
    def half(self):
        return self.size[0] / 2, self.size[1] / 2

    def inside(self, x, y):
        hx, hy = self.half
        return (np.abs(x) < hx) & (np.abs(y) < hy)

    def values_at(self, arr, x, y, fill):
        """Values of a per-pixel map aligned with the mask (e.g. pred, elev) under world points; fill off the photo."""
        fu = x / self.size[0] + 0.5
        fv = 0.5 - y / self.size[1]
        ok = (fu >= 0) & (fu < 1) & (fv >= 0) & (fv < 1)
        H, W = arr.shape
        # one gather over all points; on the photo the index is the same truncated product as before,
        # off it the clipped index is read and then replaced by fill
        r = np.minimum((np.clip(fv, 0.0, 1.0) * H).astype(np.intp), H - 1)
        c = np.minimum((np.clip(fu, 0.0, 1.0) * W).astype(np.intp), W - 1)
        return np.where(ok, arr.reshape(-1)[r * W + c], np.array(fill, arr.dtype))

    def classes_at(self, x, y):
        """Taxonomy class under world points (x, y); UNKNOWN off the photo."""
        return self.values_at(self.mask, x, y, classes.UNKNOWN)

    def hazard_distance(self, x, y):
        """Metres from (x, y) to the nearest SORA hazard pixel (inf if none).

        Computed on a dist_cell_m grid where a cell is a hazard if any pixel in
        it is, so a person a few pixels wide is not lost to the downsampling.
        """
        if self._dist is None:
            H, W = self.mask.shape
            gw = max(1, int(round(self.size[0] / self.dist_cell)))
            gh = max(1, int(round(self.size[1] / self.dist_cell)))
            hz = np.isin(self.mask, HAZARD).astype(np.float32)
            hz = cv2.resize(hz, (gw, gh), interpolation=cv2.INTER_AREA) > 0
            if not hz.any():
                self._dist = np.full((gh, gw), np.inf, np.float32)
            else:
                d = cv2.distanceTransform((~hz).astype(np.uint8), cv2.DIST_L2, 5)
                self._dist = d * np.float32(self.size[0] / gw)
        gh, gw = self._dist.shape
        fu = x / self.size[0] + 0.5
        fv = 0.5 - y / self.size[1]
        if not (0 <= fu < 1 and 0 <= fv < 1):
            return 0.0
        return float(self._dist[int(fv * gh), int(fu * gw)])

    def _sora_grid(self, sora_m):
        """SORA-safe cells (landable class throughout AND >= sora_m from a hazard), and for
        every cell the nearest SORA-safe cell and the distance to it, on the dist_cell_m grid."""
        key = round(float(sora_m), 3)
        cache = getattr(self, '_sora_cache', {})
        if key not in cache:
            self.hazard_distance(0.0, 0.0)                      # builds self._dist
            gh, gw = self._dist.shape
            landable = np.isin(self.mask, list(classes.DEFAULT_SAFE_CLASSES)).astype(np.float32)
            landable = cv2.resize(landable, (gw, gh), interpolation=cv2.INTER_AREA) > 0.999
            safe = landable & (self._dist >= sora_m)
            if safe.any():
                src = (~safe).astype(np.uint8)
                dist, lab = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
                ys, xs = np.nonzero(src == 0)
                lut = np.zeros((lab.max() + 1, 2), np.int32)
                lut[lab[ys, xs]] = np.stack([ys, xs], 1)
                near = lut[lab].astype(np.int16 if max(gh, gw) < 32767 else np.int32)
                dist = dist * np.float32(self.size[0] / gw)
            else:
                dist = np.full((gh, gw), np.inf, np.float32)
                near = np.zeros((gh, gw, 2), np.int32)
            cache[key] = (safe, dist, near)
            self._sora_cache = cache
        return cache[key]

    def _cell(self, x, y, shape):
        gh, gw = shape
        return (int(np.clip((0.5 - y / self.size[1]) * gh, 0, gh - 1)),
                int(np.clip((x / self.size[0] + 0.5) * gw, 0, gw - 1)))

    def is_sora_safe(self, x, y, sora_m=3.0):
        if not self.inside(x, y):
            return False
        safe, _, _ = self._sora_grid(sora_m)
        return bool(safe[self._cell(x, y, safe.shape)])

    def nearest_sora_safe(self, x, y, sora_m=3.0):
        """(tx, ty, distance_m) of the nearest SORA-safe point; distance inf if the scene has none."""
        safe, dist, near = self._sora_grid(sora_m)
        v, u = self._cell(x, y, safe.shape)
        gh, gw = safe.shape
        tv, tu = near[v, u]
        tx = ((tu + 0.5) / gw - 0.5) * self.size[0]
        ty = (0.5 - (tv + 0.5) / gh) * self.size[1]
        return tx, ty, float(dist[v, u])

    @classmethod
    def from_sora7(cls, mask_path, size_m, name=None, dist_cell_m=0.1):
        """A scene from a mask already in taxonomy indices (0..6, 7 = unknown), e.g. MESSI masks_sora7."""
        mask = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
        if mask is None or mask.ndim != 2:
            raise ValueError(f'{mask_path}: not a single-channel mask')
        mask = np.minimum(mask, classes.UNKNOWN).astype(np.uint8)
        stem = name or mask_path.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        return cls(mask, size_m, name=stem, dist_cell_m=dist_cell_m)

    @classmethod
    def from_messi(cls, jpg_path, mask_path, size_m=None, load_photo=False, name=None):
        """A scene from a MESSI photo and its index mask (MESSI 0..15 palette)."""
        from PIL import Image
        idx = np.array(Image.open(mask_path))
        mask = lookup_table(MESSI_TO_TAXONOMY)[idx]
        size = size_m if size_m is not None else dji_ground_size(jpg_path)
        photo = None
        if load_photo:
            photo = cv2.cvtColor(cv2.imread(jpg_path, cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        stem = name or jpg_path.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        return cls(mask, size, photo=photo, name=stem)
