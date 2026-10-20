"""Tani: AirSimNH yol nesneleri (gt8 == 7) icinde cim gibi yesil gorunen piksel payi + 2 ornek bindirme.

    ~/v3_test/venv/bin/python yol_bak.py <pilot_kareler_tani>

Yesil: G > R + 12 ve G > B + 12 (kaba renk esigi, _tahmin). Yol karosu cim kenarini da iceriyorsa
yol etiketinin bir kismi aslinda cimdir; o zaman "yol -> yumusak" hatasinin bir kismi etiket hatasidir.
"""
import csv
import os
import sys

import cv2
import numpy as np

d = sys.argv[1]
os.makedirs(os.path.join(d, 'yol_bak'), exist_ok=True)
yol = yesil = 0
ornek = []
for k in csv.DictReader(open(os.path.join(d, 'kareler.csv'))):
    i, h = int(k['i']), float(k['h'])
    if not 20 <= h <= 30:
        continue
    bgr = cv2.imread(os.path.join(d, f'{i:04d}_rgb.png')).astype(np.int16)
    gt = cv2.imread(os.path.join(d, f'{i:04d}_gt8.png'), cv2.IMREAD_UNCHANGED)
    m = gt == 7
    b, g, r = bgr[..., 0], bgr[..., 1], bgr[..., 2]
    gr = m & (g > r + 12) & (g > b + 12)
    yol += m.sum()
    yesil += gr.sum()
    if m.mean() > 0.3 and len(ornek) < 2:
        ornek.append(i)
        ust = bgr.astype(np.uint8).copy()
        ust[m] = (0.5 * ust[m] + [0, 0, 120]).astype(np.uint8)
        ust[gr] = [0, 255, 255]
        cv2.imwrite(os.path.join(d, 'yol_bak', f'{i:04d}.jpg'),
                    cv2.resize(np.concatenate([bgr.astype(np.uint8), ust], 1), None, fx=0.5, fy=0.5))
print(f'20-30 m: yol etiketli piksel {yol}, bunun yesil gorunen payi %{100 * yesil / max(yol, 1):.1f} (_tahmin); ornek {ornek}')
