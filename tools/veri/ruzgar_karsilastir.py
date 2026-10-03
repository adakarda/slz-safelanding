#!/usr/bin/env python3
"""Does the wind label do anything? Wind episode vs its windless twin.

    tools/veri/ruzgar_karsilastir.py EP_DIR [EP_DIR ...]

For the identification part of each episode (VALIDATE, ground truth above
8 m): roll / pitch RMS and their means (a steady wind needs a steady lean
into it), and horizontal drift of the Gazebo position from its median (the
mode holds the site, so a pushed aircraft shows as offset and spread).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dogrula import load_csv  # noqa: E402


def main():
    print('| bölüm | n | roll ort / RMS (°) | pitch ort / RMS (°) | yatay sapma p50 / p95 / en çok (m) |')
    print('|---|---|---|---|---|')
    for ep in sys.argv[1:]:
        d = load_csv(os.path.join(ep, 'duzenli.csv'))
        m = (d['durum'] == 2) & (d['h_gercek_zemin'] > 8.0)
        if 'x_gercek' not in d or not m.any():
            print(f'| {os.path.basename(ep.rstrip("/"))} | 0 | — | — | — |')
            continue
        r, p = np.degrees(d['roll'][m]), np.degrees(d['pitch'][m])
        x, y = d['x_gercek'][m], d['y_gercek'][m]
        dev = np.hypot(x - np.nanmedian(x), y - np.nanmedian(y))
        print(f'| {os.path.basename(ep.rstrip("/"))} | {int(m.sum())} | '
              f'{np.nanmean(r):+.2f} / {np.sqrt(np.nanmean(r ** 2)):.2f} | '
              f'{np.nanmean(p):+.2f} / {np.sqrt(np.nanmean(p ** 2)):.2f} | '
              f'{np.nanpercentile(dev, 50):.2f} / {np.nanpercentile(dev, 95):.2f} / {np.nanmax(dev):.2f} |')


if __name__ == '__main__':
    main()
