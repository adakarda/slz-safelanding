"""Duzeltme 16, H16 karar kurali (on kayitli): gozlem turunun G-C cesidi, tabanla (ayni 3 tohum, val_b32).

    python3 gozlem_karar.py

S = B_K + 0.5 B_RL - 4 max(0, T_K - 12). Cesit benimsenir, eger:
  H16a  ortalama S >= taban + 5, ve tohum ciftlerinin en az 2'sinde S >= taban-sN + 5
  H16b  ortalama B_K >= taban - 3
  H16c  ortalama T_K <= taban + 0.5 s
  H16d  ortalama kalkansiz guvensiz <= taban + 5
"""
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kararla import olc  # noqa: E402

H = os.path.expanduser('~')
s = json.load(open(f'{H}/rl_inis/arama/gozlem/gozlem_sonuc.json'))
K = f'{H}/rl_inis/kos/arama'
taban = [olc(f'{K}/t2_{s["taban"]}/eval_val_b32_10.csv')] + \
        [olc(f'{K}/t3_{s["taban"]}_s{t}/eval_val_b32_10.csv') for t in (1, 2)]
cesit = [olc(f'{d}/eval_val_b32_10.csv') for d in s['dizinler']]
ort = lambda ms, f: st.mean(f(m) for m in ms)  # noqa: E731
for ad, ms in (('taban ' + s['taban'], taban), ('cesit ' + s['cesit'], cesit)):
    print(f'{ad}: S {ort(ms, lambda m: m["S"]):.1f} {[round(m["S"], 1) for m in ms]}, '
          f'kalkan B {ort(ms, lambda m: m["rl_kalkan"]["B"]):.1f}, kalkan T {ort(ms, lambda m: m["rl_kalkan"]["T"]):.1f} s, '
          f'RL B {ort(ms, lambda m: m["rl"]["B"]):.1f}, RL guvensiz {ort(ms, lambda m: m["rl"]["U"]):.1f}')
a_t = [cesit[t]['S'] >= taban[t]['S'] + 5 for t in (0, 1, 2)]
h_a = ort(cesit, lambda m: m['S']) >= ort(taban, lambda m: m['S']) + 5 and sum(a_t) >= 2
h_b = ort(cesit, lambda m: m['rl_kalkan']['B']) >= ort(taban, lambda m: m['rl_kalkan']['B']) - 3
h_c = ort(cesit, lambda m: m['rl_kalkan']['T']) <= ort(taban, lambda m: m['rl_kalkan']['T']) + 0.5
h_d = ort(cesit, lambda m: m['rl']['U']) <= ort(taban, lambda m: m['rl']['U']) + 5
print(f'H16a {h_a} (tohum {a_t}) | H16b {h_b} | H16c {h_c} | H16d {h_d}')
print(f'KARAR: {s["cesit"]} {"benimsenir" if h_a and h_b and h_c and h_d else "benimsenmez"}')
