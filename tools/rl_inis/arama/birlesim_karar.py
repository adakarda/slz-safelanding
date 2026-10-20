"""Duzeltme 18 karar kurallari (on kayitli), val_b32, 3 tohum.

  H18  (K-C cesidi, tabanla)  ortalama S >= taban + 5 ve tohum ciftlerinin en az 2'sinde; B_K >= taban - 3;
                               T_K <= taban + 0.5 s; kalkansiz guvensiz <= taban + 5  -> cesit benimsenir
  H18b (2M, ayni modelin 1M'siyle)  ortalama S >= 1M + 3 ve tohumlarin en az 2'sinde S artiyor -> 2M kullanilir

    python3 birlesim_karar.py
"""
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kararla import olc  # noqa: E402

H = os.path.expanduser('~')
s = json.load(open(f'{H}/rl_inis/arama/birlesim/birlesim_sonuc.json'))
ort = lambda ms, f: st.mean(f(m) for m in ms)  # noqa: E731


def yaz(ad, ms):
    print(f'{ad}: S {ort(ms, lambda m: m["S"]):.1f} {[round(m["S"], 1) for m in ms]}, '
          f'kalkan B {ort(ms, lambda m: m["rl_kalkan"]["B"]):.1f}, kalkan T {ort(ms, lambda m: m["rl_kalkan"]["T"]):.1f} s, '
          f'RL B {ort(ms, lambda m: m["rl"]["B"]):.1f}, RL guvensiz {ort(ms, lambda m: m["rl"]["U"]):.1f}')


taban = [olc(c) for c in s['taban_csv']]
cesit = [olc(f'{d}/eval_val_b32_10.csv') for d in s['dizinler']]
yaz('taban ' + s['taban'], taban)
yaz('cesit ' + s['cesit'], cesit)
a_t = [cesit[t]['S'] >= taban[t]['S'] + 5 for t in (0, 1, 2)]
h_a = ort(cesit, lambda m: m['S']) >= ort(taban, lambda m: m['S']) + 5 and sum(a_t) >= 2
h_b = ort(cesit, lambda m: m['rl_kalkan']['B']) >= ort(taban, lambda m: m['rl_kalkan']['B']) - 3
h_c = ort(cesit, lambda m: m['rl_kalkan']['T']) <= ort(taban, lambda m: m['rl_kalkan']['T']) + 0.5
h_d = ort(cesit, lambda m: m['rl']['U']) <= ort(taban, lambda m: m['rl']['U']) + 5
print(f'H18: a {h_a} (tohum {a_t}) | b {h_b} | c {h_c} | d {h_d}')
print(f'KARAR: {s["cesit"]} {"benimsenir" if h_a and h_b and h_c and h_d else "benimsenmez"}')
if s.get('uzun_dizinler') and all(os.path.exists(f'{d}/eval_val_b32_10.csv') for d in s['uzun_dizinler']):
    kisa = [olc(f'{d}/eval_val_b32_10.csv') for d in s['uzun_kaynak']]
    uzun = [olc(f'{d}/eval_val_b32_10.csv') for d in s['uzun_dizinler']]
    yaz('1M', kisa)
    yaz('2M', uzun)
    b_t = [uzun[t]['S'] > kisa[t]['S'] for t in (0, 1, 2)]
    ok = ort(uzun, lambda m: m['S']) >= ort(kisa, lambda m: m['S']) + 3 and sum(b_t) >= 2
    print(f'H18b: tohum {b_t} | KARAR2M: 2M {"kullanilir" if ok else "kullanilmaz"}')
