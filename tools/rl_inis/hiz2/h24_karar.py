"""Duzeltme 24, H24 karar kurali (on kayitli): yanal hiz cesitleri (y15, y20), c23'un Tur 3'uyle, val_b32, 3 tohum.

  Bir cesit benimsenir, eger 3 tohum ortalamasinda: kalkanli T <= 15.1 s (H24a), kalkanli B >= 69.5 (H24b),
  kalkansiz guvensiz <= 18.9 (H24c). Ikisi de tutarsa skoru yuksek olan.

    python3 h24_karar.py
"""
import os
import statistics as st
import sys

H = os.path.expanduser('~')
sys.path.insert(0, f'{H}/rl_inis/arama')
from kararla import olc  # noqa: E402

K = f'{H}/rl_inis/kos'
C23 = [f'{K}/arama/t2_c23_b1_adim05_alcal1', f'{K}/arama/t3_c23_b1_adim05_alcal1_s1', f'{K}/arama/t3_c23_b1_adim05_alcal1_s2']


def ort(ms, f):
    return st.mean(f(m) for m in ms)


def yaz(ad, ms):
    print(f'{ad:5s} S {ort(ms, lambda m: m["S"]):5.1f} {[round(m["S"], 1) for m in ms]} | kalkan B '
          f'{ort(ms, lambda m: m["rl_kalkan"]["B"]):5.1f} T {ort(ms, lambda m: m["rl_kalkan"]["T"]):5.1f} s | RL B '
          f'{ort(ms, lambda m: m["rl"]["B"]):5.1f} T {ort(ms, lambda m: m["rl"]["T"]):5.1f} s guvensiz '
          f'{ort(ms, lambda m: m["rl"]["U"]):5.1f}')


yaz('c23', [olc(f'{d}/eval_val_b32_10.csv') for d in C23])
kabul = []
for ad in ('y15', 'y20'):
    yol = [f'{K}/hiz2/{ad}_s{t}/eval_val_b32_10.csv' for t in (0, 1, 2)]
    if not all(os.path.exists(p) for p in yol):
        print(f'{ad}: degerlendirme eksik')
        continue
    ms = [olc(p) for p in yol]
    yaz(ad, ms)
    a = ort(ms, lambda m: m['rl_kalkan']['T']) <= 15.1
    b = ort(ms, lambda m: m['rl_kalkan']['B']) >= 69.5
    c = ort(ms, lambda m: m['rl']['U']) <= 18.9
    print(f'      H24a {a} | H24b {b} | H24c {c}')
    if a and b and c:
        kabul.append((ort(ms, lambda m: m['S']), ad))
print(f'KARAR: yanal hiz {max(kabul)[1]} benimsenir' if kabul else 'KARAR: hicbir yanal hiz cesidi H24\'u saglamadi')
