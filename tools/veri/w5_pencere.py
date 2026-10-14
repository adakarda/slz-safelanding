#!/usr/bin/env python3
"""W5's information window, from the geometry at VALIDATE entry (rule frozen 2026-10-15, K16).

    tools/veri/w5_pencere.py BOLUM [BOLUM ...] [--yalniz-tahmin] [--csv DOSYA]

The image methods learn only while the whole platform top is in view
(view_bounded). Whether that ever happens on a descent is decided before the
descent: by where VALIDATE starts. This applies one rule, frozen before
dilim 1 and not to be tuned on its results (K16, K18):

  pay = ln(h0 / h_doy)
    h0     true camera height above the platform at VALIDATE entry
           (maske_olaylari.csv h_kamera_gercek, interpolated to t_validate)
    h_doy  the camera height above which every corner of the platform top
           is inside the footprint, for the true position and yaw at
           VALIDATE entry (duzenli.csv x_gercek, y_gercek, yaw): forward
           +-0.889 h, sideways +-1.1855 h (320x240, HFOV 99.7 deg; image top
           = the nose). Corners: the target's rectangle in the world yaml.
  grup     = pencereli if pay >= 0.05, else penceresiz
  sinirda  = 0 <= pay < 0.10 (within 0.05 of the threshold either way)
  pay < 0  = the platform never fits: penceresiz, not borderline

Measured check (not part of the rule): pencereli_olcum = at least 10 frames
with the region in view (view_bounded and rho > 0) between VALIDATE and the
Gazebo touchdown. On the 21 recorded W5 episodes (4 seeds) the rule agreed
21/21; with 4 seeds that is about 4 independent geometries, not 21.

--yalniz-tahmin writes the rule's columns only, before anyone looks at the
frame counts (the blind half of the comparison).
"""
import argparse
import csv
import json
import math
import os
import sys

import numpy as np
import yaml

ILERI, YAN = 0.889, 1.1855
ESIK, SINIR_ALT, SINIR_UST = 0.05, 0.0, 0.10
PENCERE_KARE = 10


def _oku(yol, sutunlar):
    with open(yol, newline='') as f:
        r = csv.reader(f)
        bas = next(r)
        ix = [bas.index(s) for s in sutunlar]
        satir = list(r)
    return {s: np.array([float(x[i]) if i < len(x) and x[i] not in ('', 'None', 'nan') else np.nan
                         for x in satir]) for s, i in zip(sutunlar, ix)}


def koseler(dunya_yaml):
    w = yaml.safe_load(open(dunya_yaml))
    hedef = next(s for s in w['yuzeyler'] if s.get('ad') == w['hedef'])
    x0, y0, x1, y1 = hedef['dikdortgenler'][0]
    return [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]


def h_doy(x, y, yaw_ned, kose):
    f = (math.sin(yaw_ned), math.cos(yaw_ned))        # forward, ENU (east, north)
    r = (math.cos(yaw_ned), -math.sin(yaw_ned))       # right
    gerek = 0.0
    for cx, cy in kose:
        vx, vy = cx - x, cy - y
        gerek = max(gerek, abs(vx * f[0] + vy * f[1]) / ILERI, abs(vx * r[0] + vy * r[1]) / YAN)
    return gerek


def pencere(bolum, olcum=True):
    oz = json.load(open(os.path.join(bolum, 'ep_ozet.json')))
    kos = yaml.safe_load(open(os.path.join(bolum, 'kosul.yaml')))
    t0, t1 = oz.get('t_validate'), oz.get('t_temas_gercek')
    out = dict(bolum=os.path.basename(os.path.normpath(bolum)), tohum=kos.get('tohum'),
               kol=kos.get('kol'), t_validate=t0)
    if t0 is None:
        out.update(grup='VALIDATE yok')
        return out
    d = _oku(os.path.join(bolum, 'duzenli.csv'), ('t_gz', 'x_gercek', 'y_gercek', 'yaw'))
    s = np.argsort(d['t_gz'])
    i0 = int(np.searchsorted(d['t_gz'][s], t0))
    x, y, yaw = (d[k][s][i0] for k in ('x_gercek', 'y_gercek', 'yaw'))
    m = _oku(os.path.join(bolum, 'maske_olaylari.csv'),
             ('t_yakalama', 'h_kamera_gercek', 'view_bounded', 'rho'))
    ok = np.isfinite(m['h_kamera_gercek'])
    h0 = float(np.interp(t0, m['t_yakalama'][ok], m['h_kamera_gercek'][ok]))
    hd = h_doy(x, y, yaw, koseler(kos['dunya_yaml']))
    pay = math.log(h0 / hd)
    out.update(h0_m=round(h0, 3), h_doy_m=round(hd, 3), pay=round(pay, 4),
               merkezden_m=round(math.hypot(x, y), 2),
               grup='pencereli' if pay >= ESIK else 'penceresiz',
               sinirda=int(SINIR_ALT <= pay < SINIR_UST))
    if olcum and t1 is not None:
        sel = ((m['t_yakalama'] >= t0) & (m['t_yakalama'] <= t1) & (m['view_bounded'] == 1)
               & (m['rho'] > 0))
        n = int(sel.sum())
        out.update(sinirli_kare=n, grup_olcum='pencereli' if n >= PENCERE_KARE else 'penceresiz')
        out['uyusma'] = int(out['grup'] == out['grup_olcum'])
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('bolum', nargs='+')
    p.add_argument('--yalniz-tahmin', action='store_true')
    p.add_argument('--csv', default=None)
    a = p.parse_args()
    satir = [pencere(b, olcum=not a.yalniz_tahmin) for b in a.bolum]
    alan = []
    for s in satir:
        alan += [k for k in s if k not in alan]
    yaz = csv.DictWriter(open(a.csv, 'w', newline='') if a.csv else sys.stdout, fieldnames=alan)
    yaz.writeheader()
    yaz.writerows(satir)
    if not a.yalniz_tahmin:
        u = [s['uyusma'] for s in satir if 'uyusma' in s]
        print(f'# kural ile olcum uyusmasi: {sum(u)}/{len(u)}', file=sys.stderr)


if __name__ == '__main__':
    main()
