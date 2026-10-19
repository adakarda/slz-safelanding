"""Egitim surerken hiz ve basari: kosularin monitor dosyalarindan, ayni adim araliginda (tanimlayici).

    python3 hiz_izle.py d_D1_s0 b_B1_s0 ...

Her kosu icin son 1500 bolum (ya da verilen adima kadar olanlar): egitimdeki zemin basarisi ve basarili bolumlerin
ortalama suresi (adim x 0.25 s). D egitimde 30 s, B 90 s sinirla egitildi: egitim icindeki basari oranlari bu yuzden
dogrudan kiyaslanmaz; sure (yalniz basarililar) kiyaslanabilir.
"""
import csv
import glob
import os
import sys

import numpy as np

K = os.path.expanduser('~/rl_inis/kos')


def oku(kosu):
    rows = []
    for f in sorted(glob.glob(os.path.join(K, kosu, 'monitor_[0-9]*.monitor.csv'))):
        rows += list(csv.DictReader(l for l in open(f) if not l.startswith('#')))
    rows.sort(key=lambda r: float(r['t']))
    adim = np.cumsum([int(r['l']) for r in rows])
    return rows, adim


hedef_adim = None
for kosu in sys.argv[1:]:
    rows, adim = oku(kosu)
    if hedef_adim is None:
        hedef_adim = int(adim[-1]) if len(adim) else 0
    sec = [r for r, a in zip(rows, adim) if a <= hedef_adim][-1500:]
    ok = [r for r in sec if r['zemin_success'] == 'True']
    sure = np.mean([int(r['l']) * 0.25 for r in ok]) if ok else float('nan')
    print(f'{kosu:10s} {hedef_adim:>8d} adima kadar son {len(sec)} bolum: basari {100 * len(ok) / max(len(sec), 1):5.1f} %, '
          f'basarili bolum suresi {sure:5.1f} s, sure doldu {100 * sum(r["outcome"] == "timeout" for r in sec) / max(len(sec), 1):5.1f} %')
