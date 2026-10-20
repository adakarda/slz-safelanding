"""Duzeltme 19, H19 (on kayitli): B2-s0'in ince ayarli cesitleri, B2-s0 ile (val_b32, 320 deneme, tek tohum).

Cesit kabul edilir, eger:  T_K <= B2-s0 T_K - 1.5 s  ve  B_K >= B2-s0 B_K - 3  ve  kalkansiz guvensiz <= B2-s0 + 5.
Birden cok cesit kabul edilirse skoru (S) en yuksek olan "hizlandirilmis B2" olur.

    python3 b2hiz_karar.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kararla import olc  # noqa: E402

H = os.path.expanduser('~')
b2 = olc(f'{H}/rl_inis/kos/b_B2_s0/eval_val.csv')


def yaz(ad, m):
    print(f'{ad:14s} S {m["S"]:5.1f} | kalkan B {m["rl_kalkan"]["B"]:5.1f} T {m["rl_kalkan"]["T"]:5.1f} s | '
          f'RL B {m["rl"]["B"]:5.1f} T {m["rl"]["T"]:5.1f} s guvensiz {m["rl"]["U"]:5.1f}')


yaz('B2-s0', b2)
kabul = []
for c in ('h1_hiz', 'h2_hiz_45s', 'h3_hiz_kalkan'):
    p = f'{H}/rl_inis/kos/b2hiz/{c}/eval_val_b32_10.csv'
    if not os.path.exists(p):
        print(f'{c}: degerlendirme yok')
        continue
    m = olc(p)
    yaz(c, m)
    ok = (m['rl_kalkan']['T'] <= b2['rl_kalkan']['T'] - 1.5 and m['rl_kalkan']['B'] >= b2['rl_kalkan']['B'] - 3
          and m['rl']['U'] <= b2['rl']['U'] + 5)
    if ok:
        kabul.append((m['S'], c))
print(f'KARAR: hizlandirilmis B2 = {max(kabul)[1]}' if kabul else 'KARAR: hicbir cesit H19\'u saglamadi; B2-s0 aynen kalir')
