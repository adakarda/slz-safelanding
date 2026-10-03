#!/usr/bin/env python3
"""World geometry for ground truth: surface heights and the target surface.

Gazebo publishes where the aircraft is, not what is under it. The worlds are
built from flat boxes, so the height of the ground at (x, y) is known exactly
from the world description; this module reads it from the world's yaml.

Format (world frame, metres, x east, y north):

    dunya_id: W3
    zemin_z: 0.0                    # the ground plane
    hedef: ada                      # name of the intended landing surface
    yuzeyler:
      - ad: ada
        z: 0.02                     # top of the surface
        inilebilir: true
        dikdortgenler: [[x0, y0, x1, y1], ...]   # union of rectangles
        daireler: [[cx, cy, r], ...]             # and/or discs
        alan_m2: 100.0

A missing file means the existing open-field world: flat ground at z = 0, no
designated target surface.
"""
import math

import yaml


class Dunya:
    def __init__(self, path=None):
        self.spec = {}
        if path:
            with open(path) as f:
                self.spec = yaml.safe_load(f) or {}
        self.dunya_id = self.spec.get('dunya_id', 'acik_alan')
        self.zemin_z = float(self.spec.get('zemin_z', 0.0))
        self.yuzeyler = self.spec.get('yuzeyler', []) or []
        hedef = self.spec.get('hedef')
        self.hedef = next((s for s in self.yuzeyler if s.get('ad') == hedef), None)

    @staticmethod
    def _icinde(s, x, y) -> bool:
        for x0, y0, x1, y1 in s.get('dikdortgenler', []) or []:
            if min(x0, x1) <= x <= max(x0, x1) and min(y0, y1) <= y <= max(y0, y1):
                return True
        for cx, cy, r in s.get('daireler', []) or []:
            if math.hypot(x - cx, y - cy) <= r:
                return True
        return False

    def yuzey_z(self, x: float, y: float) -> float:
        """Height of whatever surface is under (x, y)."""
        z = self.zemin_z
        for s in self.yuzeyler:
            if self._icinde(s, x, y):
                z = max(z, float(s.get('z', self.zemin_z)))
        return z

    def hedef_z(self) -> float:
        return float(self.hedef.get('z', self.zemin_z)) if self.hedef else self.zemin_z

    def hedef_alan(self) -> float:
        return float(self.hedef['alan_m2']) if self.hedef and 'alan_m2' in self.hedef \
            else float('nan')

    def hedef_merkez(self):
        if not self.hedef:
            return None
        m = self.hedef.get('merkez')
        return (float(m[0]), float(m[1])) if m else None

    def hedefte_mi(self, x: float, y: float):
        """True/False if a target is defined, None for the open field.

        On the target and not on anything non-landable standing on it (W8's
        centre obstacle sits inside the island's rectangle)."""
        if not self.hedef:
            return None
        if not self._icinde(self.hedef, x, y):
            return False
        top = float(self.hedef.get('z', self.zemin_z))
        for s in self.yuzeyler:
            if s is self.hedef or s.get('inilebilir', True):
                continue
            if float(s.get('z', 0.0)) > top and self._icinde(s, x, y):
                return False
        return True
