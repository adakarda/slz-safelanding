"""Kollarin val_b32 ozeti (kalkansiz RL): basari, guvensiz, sure doldu, basarili inis suresi; tohum basina.

    python3 kol_ozet.py b_B1 d_D1 ...
"""
import csv
import os
import statistics as st
import sys

K = os.path.expanduser('~/rl_inis/kos')
for kol in sys.argv[1:]:
    for t in (0, 1, 2):
        f = os.path.join(K, f'{kol}_s{t}', 'eval_val.csv')
        if not os.path.exists(f):
            continue
        rs = [r for r in csv.DictReader(open(f)) if r['method'] == 'rl']
        n = len(rs)
        ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
        guv = sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs)
        tout = sum(r['outcome'] == 'timeout' for r in rs)
        print(f'{kol}_s{t}: basari {100 * len(ok) / n:5.1f} %, guvensiz {100 * guv / n:5.1f} %, sure doldu {100 * tout / n:5.1f} %, '
              f'basarili inis suresi {st.mean(ok):5.1f} s')
