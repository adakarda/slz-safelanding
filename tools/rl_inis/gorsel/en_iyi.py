"""Gorsellestirilecek en iyi kosu dizini: 'arama' = taramanin Tur 3'unde ortalama S'si en yuksek ayarin tohum 0'i (t2_);
'gozlem' = gozlem turunun G-C cesidinin tohum 0'i. Yoksa bos cikti.

    python3 en_iyi.py arama|gozlem
"""
import csv
import glob
import json
import os
import statistics as st
import sys

H = os.path.expanduser('~')


def S(yol):
    rs = list(csv.DictReader(open(yol)))
    m = {}
    for y in ('rl', 'rl_kalkan'):
        s = [r for r in rs if r['method'] == y]
        ok = [float(r['t']) for r in s if r['zemin_success'] == '1']
        m[y] = (100 * len(ok) / len(s), st.mean(ok) if ok else 30.0)
    return m['rl_kalkan'][0] + 0.5 * m['rl'][0] - 4 * max(0.0, m['rl_kalkan'][1] - 12.0)


if sys.argv[1] == 'arama':
    a = f'{H}/rl_inis/kos/arama'
    puan = {}
    for t2 in glob.glob(f'{a}/t2_*/eval_val_b32_10.csv'):
        ad = os.path.basename(os.path.dirname(t2))[3:]
        cs = [t2] + [f'{a}/t3_{ad}_s{t}/eval_val_b32_10.csv' for t in (1, 2)]
        if all(os.path.exists(c) for c in cs):
            puan[ad] = st.mean(S(c) for c in cs)
    if puan:
        print(f'{a}/t2_{max(puan, key=puan.get)}')
else:
    g = f'{H}/rl_inis/arama/gozlem/gozlem_sonuc.json'
    if os.path.exists(g):
        print(json.load(open(g))['dizinler'][0])
