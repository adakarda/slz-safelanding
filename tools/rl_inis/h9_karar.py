"""Duzeltme 9 karar kurali (on kayitli), B deneyinin 9 kosusu uzerinde (val_b32, 320 deneme / kosu).

    python3 h9_karar.py

Zemin kuraliyla: basari = zemin_success; guvensiz = indi ama zemin_success degil (outcome landing);
yumusak pay = basarili inisler icinde soft. Birincil olcut RL'nin kalkansiz zemin basarisi.
H9a: B1 guvensiz <= 0.75 x B0 | H9b: B1 basari >= B0 + 5 | H9c: B1 yumusak pay > B0 | H9d: B2 basari >= B1 + 3.
Karar: H9a ve H9b ortalamada saglanir ve 3 tohumun en az 2'sinde ayni yondeyse zemin_v1 benimsenir;
H9d saglanirsa aynalama da.
"""
import csv
import os
import statistics as st

K = os.path.expanduser('~/rl_inis/kos')


def olc(kol, tohum, yontem='rl'):
    rs = [r for r in csv.DictReader(open(os.path.join(K, f'b_{kol}_s{tohum}', 'eval_val.csv'))) if r['method'] == yontem]
    n = len(rs)
    basari = [r for r in rs if r['zemin_success'] == '1']
    indi = [r for r in rs if r['outcome'] in ('safe_landing', 'unsafe_landing')]
    guv = [r for r in indi if r['zemin_success'] != '1']
    return {'basari': 100 * len(basari) / n, 'guvensiz': 100 * len(guv) / n,
            'yumusak_pay': 100 * sum(r['soft'] == '1' for r in basari) / max(len(basari), 1),
            'sora': 100 * sum(r['sora_success'] == '1' for r in rs) / n,
            'sure': 100 * sum(r['outcome'] == 'timeout' for r in rs) / n}


def ozet(v):
    return f'{st.mean(v):5.1f} ± {st.stdev(v):4.1f}'


for yontem in ('rl', 'rl_kalkan'):
    print(f'== {yontem} (val_b32, 320 deneme / kosu)')
    m = {(k, t): olc(k, t, yontem) for k in ('B0', 'B1', 'B2') for t in (0, 1, 2)}
    print(f'{"kol":4s} {"zemin basari":>14s} {"guvensiz":>14s} {"yumusak pay":>14s} {"SORA":>14s} {"sure doldu":>14s}')
    for k in ('B0', 'B1', 'B2'):
        print(f'{k:4s} ' + ' '.join(f'{ozet([m[k, t][a] for t in (0, 1, 2)]):>14s}'
                                     for a in ('basari', 'guvensiz', 'yumusak_pay', 'sora', 'sure')))
    if yontem != 'rl':
        continue
    ort = lambda k, a: st.mean(m[k, t][a] for t in (0, 1, 2))  # noqa: E731
    a_t = [m['B1', t]['guvensiz'] <= 0.75 * m['B0', t]['guvensiz'] for t in (0, 1, 2)]
    b_t = [m['B1', t]['basari'] >= m['B0', t]['basari'] + 5 for t in (0, 1, 2)]
    c_t = [m['B1', t]['yumusak_pay'] > m['B0', t]['yumusak_pay'] for t in (0, 1, 2)]
    d_t = [m['B2', t]['basari'] >= m['B1', t]['basari'] + 3 for t in (0, 1, 2)]
    h9a = ort('B1', 'guvensiz') <= 0.75 * ort('B0', 'guvensiz')
    h9b = ort('B1', 'basari') >= ort('B0', 'basari') + 5
    h9c = ort('B1', 'yumusak_pay') > ort('B0', 'yumusak_pay')
    h9d = ort('B2', 'basari') >= ort('B1', 'basari') + 3
    print(f'H9a ortalama {h9a}, tohum {a_t} | H9b ortalama {h9b}, tohum {b_t} | H9c ortalama {h9c}, tohum {c_t} | '
          f'H9d ortalama {h9d}, tohum {d_t}')
    zemin = h9a and h9b and sum(a_t) >= 2 and sum(b_t) >= 2
    print(f'KARAR: zemin_v1 {"benimsenir" if zemin else "benimsenmez"}; aynalama '
          f'{"benimsenir" if zemin and h9d and sum(d_t) >= 2 else "benimsenmez"}')
