"""Hiz yamasi 2 (sonuc birebir ayni): harita okuma tek toplama ile; 3-vektor capraz carpim elle.
Kullanim: python yama_hiz2.py <eland_rl paket klasoru>"""
import os
import sys

d = sys.argv[1]


def patch(name, pairs):
    p = os.path.join(d, name)
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (name, old[:60])
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)


patch('scene.py', [
    ('''    def values_at(self, arr, x, y, fill):
        """Values of a per-pixel map aligned with the mask (e.g. pred, elev) under world points; fill off the photo."""
        fu = x / self.size[0] + 0.5
        fv = 0.5 - y / self.size[1]
        ok = (fu >= 0) & (fu < 1) & (fv >= 0) & (fv < 1)
        out = np.full(np.shape(x), fill, arr.dtype)
        H, W = arr.shape
        out[ok] = arr[(fv[ok] * H).astype(np.intp), (fu[ok] * W).astype(np.intp)]
        return out

    def classes_at(self, x, y):
        """Taxonomy class under world points (x, y); UNKNOWN off the photo."""
        fu = x / self.size[0] + 0.5
        fv = 0.5 - y / self.size[1]
        ok = (fu >= 0) & (fu < 1) & (fv >= 0) & (fv < 1)
        out = np.full(np.shape(x), classes.UNKNOWN, np.uint8)
        H, W = self.mask.shape
        out[ok] = self.mask[(fv[ok] * H).astype(np.intp), (fu[ok] * W).astype(np.intp)]
        return out''',
     '''    def values_at(self, arr, x, y, fill):
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
        return self.values_at(self.mask, x, y, classes.UNKNOWN)'''),
])

patch('camera.py', [
    ('''    c1 = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    b2 = np.cross(b3, c1)
    b2 /= np.linalg.norm(b2)
    b1 = np.cross(b2, b3)
    return np.stack([b1, b2, b3], 1)''',
     '''    c1 = (math.cos(yaw), math.sin(yaw), 0.0)
    b2 = np.array(_cross(b3, c1))
    b2 /= np.linalg.norm(b2)
    b1 = np.array(_cross(b2, b3))
    return np.stack([b1, b2, b3], 1)


def _cross(a, b):
    """np.cross for two 3-vectors, same products and differences, without its per-call overhead."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])'''),
])
print('hiz yamasi 2 tamam:', d)
