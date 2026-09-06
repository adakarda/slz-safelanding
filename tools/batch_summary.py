#!/usr/bin/env python3
"""Summarise a batch CSV: success rate and the spread of every metric.

Median and interquartile range rather than mean and standard deviation. These
distributions are small, skewed and occasionally contain a run that went badly
in a way no average should be allowed to hide -- and the thing a reader wants
from "does it land" is not a mean anyway.
"""
import csv
import sys

import numpy as np

FIELDS = [('descent_s', 's', 'alcalma suresi'),
          ('err_rms', 'm/s', 'dikey hiz RMS takip hatasi'),
          ('err_mean', 'm/s', 'dikey hiz ortalama hata'),
          ('candidate_hz', 'Hz', 'aday yayin hizi'),
          ('invalid_frames', '', 'aday uretilmeyen kare'),
          ('gaps_over_3s', '', '3 s ustu aday boslugu'),
          ('site_jumps', '', 'site sicramasi >4 m'),
          ('transitions', '', 'durum gecisi'),
          ('aborts', '', 'ABORT'),
          ('site_risk', '', 'inilen yerin risk skoru'),
          ('site_clearance_m', 'm', 'inilen yerin acikligi'),
          ('touchdown_err_m', 'm', 'dokunmanin siteden sapmasi')]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/eland_batch.csv'
    with open(path, newline='') as f:
        rows = [r for r in csv.DictReader(f)]
    if not rows:
        print('satir yok')
        return 1

    landed = [r for r in rows if r.get('landed') == '1']
    print(f'kosu sayisi        : {len(rows)}')
    print(f'inis tamamlanan    : {len(landed)}/{len(rows)} '
          f'({100.0 * len(landed) / len(rows):.0f} %)')
    scored = landed or rows
    for key, unit, label in FIELDS:
        vals = []
        for r in scored:
            try:
                vals.append(float(r[key]))
            except (KeyError, TypeError, ValueError):
                continue
        if not vals:
            continue
        v = np.asarray(vals)
        q1, med, q3 = np.percentile(v, [25, 50, 75])
        u = f' {unit}' if unit else ''
        print(f'{label:26s}: ortanca {med:6.2f}{u}  '
              f'[{q1:.2f}, {q3:.2f}]  en kotu {v.max():.2f}  n={len(v)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
