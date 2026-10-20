"""M0 pilotu, tani: v3'un ham 8 sinifi (7 = yol) ile yakala.py --tani'nin _gt8.png'si.

    ~/v3_test/venv/bin/python v3_tani.py <kare klasoru> [--fov 99.7]

Soru: terrain-hazard hatalari (gercek 2 -> v3 0/1) yoldan mi, bitki ortusunden mi geliyor?
"""
import argparse
import collections
import csv
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, '/home/arda/v3_test/model')
import v3_model as M  # noqa: E402

AD = ['yumusak', 'sert', 'arazi', 'yapi', 'su', 'arac', 'insan', 'yol']


def yaz(cm, baslik):
    n = cm.sum()
    print(f'{baslik}: {cm.trace() / n:.3f} piksel dogrulugu; satir gercek, sutun v3 (%), | gercek pay %')
    print('            ' + ' '.join(f'{x[:5]:>5}' for x in AD))
    for c in range(8):
        if cm[c].sum():
            print(f'   {AD[c]:>7}  ' + ' '.join(f'{100 * v / cm[c].sum():5.1f}' for v in cm[c]) +
                  f'  | {100 * cm[c].sum() / n:5.1f}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('klasor')
    ap.add_argument('--fov', type=float, default=99.7)
    a = ap.parse_args()
    model = M.yukle('/home/arda/v3_test/model/best_v3.pth')
    top = collections.defaultdict(lambda: np.zeros((8, 8), np.int64))
    for k in csv.DictReader(open(os.path.join(a.klasor, 'kareler.csv'))):
        i, h = int(k['i']), float(k['h'])
        bgr = cv2.imread(os.path.join(a.klasor, f'{i:04d}_rgb.png'))
        gt = cv2.imread(os.path.join(a.klasor, f'{i:04d}_gt8.png'), cv2.IMREAD_UNCHANGED)
        gsd = 2 * h * math.tan(math.radians(a.fov) / 2) / bgr.shape[1] * 100
        pred = M.segmentle(model, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), gsd_cm=gsd, sim_siniflari=False)
        ok = gt < 8
        top[h] += np.bincount(gt[ok].astype(np.int64) * 8 + pred[ok], minlength=64).reshape(8, 8)
    for h in sorted(top):
        yaz(top[h], f'{h:.0f} m')
    yaz(sum(top[h] for h in top if 20 <= h <= 30), '20-30 m birlikte')


if __name__ == '__main__':
    main()
