"""Hiz yamasi (sonuc birebir ayni): tutum matrisi sadece kameranin kullandigi kayit icin hesaplanir;
sora_channel'da np.isin yerine uint8 arama tablosu. Kullanim: python yama_hiz.py <eland_rl paket klasoru>"""
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


patch('dynamics.py', [
    ("        self.history.append((self.t, self.pos.copy(), self.attitude()))\n\n    def attitude(self):",
     "        self.history.append(self._record())\n\n    def attitude(self):"),
    ("""        return v[axis]
""", """        return v[axis]

    def _record(self):
        # the attitude is computed later, only for the record the camera actually uses (delayed_pose):
        # same rotation() on the same numbers, ~5x fewer calls
        return [self.t, self.pos.copy(), self.acc.copy(), self.yaw, None]

    def _rotation_of(self, rec):
        if rec[4] is None:
            a = rec[2]
            rec[4] = rotation((a[0] + self._bias[0], a[1] + self._bias[1], max(G + a[2], 1.0)), rec[3])
        return rec[4]
"""),
    ("            self.history.append((self.t, self.pos.copy(), self.attitude()))\n",
     "            self.history.append(self._record())\n"),
    ("""        for t, pos, R in self.history:       # oldest first; first one not too old wins
            if t >= target - 1e-9:
                return pos, R
        return self.history[-1][1], self.history[-1][2]""",
     """        for rec in self.history:             # oldest first; first one not too old wins
            if rec[0] >= target - 1e-9:
                return rec[1], self._rotation_of(rec)
        return self.history[-1][1], self._rotation_of(self.history[-1])"""),
])

patch('camera.py', [
    ("""import math

import cv2""", """import functools
import math

import cv2"""),
    ("""def sora_channel(""", """@functools.lru_cache(maxsize=None)
def _class_table(classes):
    t = np.zeros(256, bool)
    t[list(classes)] = True
    return t


def _in_classes(img, classes):
    \"\"\"np.isin(img, classes) for small class lists; a lookup table when img is uint8.\"\"\"
    if img.dtype == np.uint8:
        return _class_table(tuple(classes))[img]
    return np.isin(img, classes)


def sora_channel("""),
    ("    hazard = np.isin(sq, hazard_classes)\n", "    hazard = _in_classes(sq, hazard_classes)\n"),
    ("    ok = np.isin(sq, safe_classes) & (dist_px * px_m >= sora_m)\n",
     "    ok = _in_classes(sq, safe_classes) & (dist_px * px_m >= sora_m)\n"),
])
print('hiz yamasi tamam:', d)
