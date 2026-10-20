"""Duzeltme 7 karar kurali (on kayitli): PB, PC ya da PD, PA'ya gore RL veya RL + kalkan icin SORA basarisini
>= 3 puan artirmali ya da guvensiz inisi >= %25 (goreli) azaltmali; oteki metrigi 3 puandan fazla kotulestirmemeli.

    python3 h7_karar.py
"""
import ast
import os
import re

K = os.path.expanduser('~/rl_inis/kos')


def oku(kol):
    f = os.path.join(K, f'da_{kol}', 'eval_test_foto.txt')
    out = {}
    for ln in open(f):
        m = re.match(r'^(\w+)\s+SORA basari\s+([\d.]+) %.*?(\{.*\})\s*$', ln)
        if m and m.group(1) in ('rl', 'rl_kalkan'):
            d = ast.literal_eval(m.group(3))
            n = sum(d.values())
            out[m.group(1)] = (float(m.group(2)), 100.0 * d.get('unsafe_landing', 0) / n, n)
    return out


pa = oku('PA')
print('PA', {k: f'SORA {v[0]:.1f}, guvensiz {v[1]:.1f} (n {v[2]})' for k, v in pa.items()})
for kol in ('P0', 'PB', 'PC', 'PD'):
    r = oku(kol)
    satir = []
    for yon in ('rl', 'rl_kalkan'):
        s, g, _ = r[yon]
        s0, g0, _ = pa[yon]
        a = s - s0 >= 3.0 and (g - g0) <= 3.0
        b = g0 > 0 and (g0 - g) / g0 >= 0.25 and (s0 - s) <= 3.0
        satir.append(f'{yon}: SORA {s:.1f} ({s - s0:+.1f}), guvensiz {g:.1f} ({g - g0:+.1f}) -> {"SAGLAR" if a or b else "saglamaz"}')
    print(kol, ' | '.join(satir))
