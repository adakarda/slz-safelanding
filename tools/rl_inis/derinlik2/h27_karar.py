"""Duzeltme 27, H27 karar kurali (on kayitli). 3 tohum ortalamasi, yontem rl_kalkan2 (son sistem), kiyas A_irtifa.
  H27b (derinlik kanali gereksiz mi): B_yok basari >= A - 2 ve sure <= A + 0.5 s ise "irtifa kanali gerekmiyor".
  H27c (Depth Anything): C_da (basari >= A + 3 ya da (sure <= A - 1.0 s ve basari >= A - 1)) ve guvensiz <= A + 2
        ise "Depth Anything eklemeye deger" (sahada calistirilmasi ayri bir is).
Tanimlayici: yalin RL (rl) de raporlanir.

    python3 h27_karar.py
"""
import csv
import os
import statistics as st

K = os.path.expanduser('~/rl_inis/kos/derinlik2')
KOLLAR = ('A_irtifa', 'B_yok', 'C_da')


def olc(p, y):
    rs = [r for r in csv.DictReader(open(p)) if r['method'] == y]
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return dict(B=100 * len(ok) / len(rs), T=st.mean(ok) if ok else 30.0,
                U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / len(rs))


yol = {k: [f'{K}/{k}_s{t}/deger.csv' for t in (0, 1, 2)] for k in KOLLAR}
if not all(os.path.exists(p) for ps in yol.values() for p in ps):
    print('KARAR: degerlendirmeler eksik')
    raise SystemExit
m = {}
for y in ('rl', 'rl_kalkan2'):
    for k in KOLLAR:
        v = [olc(p, y) for p in yol[k]]
        m[(k, y)] = {x: st.mean(d[x] for d in v) for x in 'BTU'}
        print(f'{y:11s} {k:9s} basari {m[(k, y)]["B"]:5.1f} {[round(d["B"], 1) for d in v]} | sure {m[(k, y)]["T"]:5.2f} s'
              f' | guvensiz {m[(k, y)]["U"]:4.1f}')
A, Bk, C = (m[(k, 'rl_kalkan2')] for k in KOLLAR)
h27b = Bk['B'] >= A['B'] - 2 and Bk['T'] <= A['T'] + 0.5
h27c = (C['B'] >= A['B'] + 3 or (C['T'] <= A['T'] - 1.0 and C['B'] >= A['B'] - 1)) and C['U'] <= A['U'] + 2
print(f'H27b {h27b} -> ' + ('irtifa kanali gerekmiyor' if h27b else 'irtifa kanali gerekli'))
print(f'H27c {h27c} -> ' + ('Depth Anything eklemeye deger' if h27c else 'Depth Anything eklenmez'))
