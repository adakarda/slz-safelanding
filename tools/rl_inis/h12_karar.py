"""Duzeltme 12 karar kurali (on kayitli): D1 (egitimde 30 s) ile kiyas (C1 ya da B1, D1'in odulune gore), ayni tohumlar.

    python3 h12_karar.py

H12a: D1 RL basari >= kiyas + 5 | H12b: D1 RL + kalkan basari >= kiyas + 5 | H12c: D1 RL guvensiz <= kiyas + 5.
Karar: H12a ve H12c ortalamada ve tohum ciftlerinin en az 2'sinde saglanirsa egitimde 30 s benimsenir.
"""
import csv
import json
import os
import statistics as st

K = os.path.expanduser('~/rl_inis/kos')
odul = json.load(open(os.path.join(K, 'd_D1_s0', 'args.json')))['reward']
KOL = {'kiyas': 'c_C1_s{}' if odul == 'zemin_v2' else 'b_B1_s{}', 'D1': 'd_D1_s{}'}
print(f'D1 odulu {odul}; kiyas {KOL["kiyas"].format("N")}')


def olc(kol, t, yontem):
    f = os.path.join(K, KOL[kol].format(t), 'eval_val.csv')
    if not os.path.exists(f):
        return None
    rs = [r for r in csv.DictReader(open(f)) if r['method'] == yontem]
    n = len(rs)
    pay = lambda k: 100 * sum(k(r) for r in rs) / n  # noqa: E731
    return {'basari': pay(lambda r: r['zemin_success'] == '1'),
            'guvensiz': pay(lambda r: r['outcome'] in ('safe_landing', 'unsafe_landing') and r['zemin_success'] != '1'),
            'sure': pay(lambda r: r['outcome'] == 'timeout'),
            'yumusak': pay(lambda r: r['soft'] == '1')}


ozet = lambda v: f'{st.mean(v):5.1f} ± {st.stdev(v):4.1f}'  # noqa: E731
m = {(k, y, t): olc(k, t, y) for k in KOL for y in ('rl', 'rl_kalkan') for t in (0, 1, 2)}
for y in ('rl', 'rl_kalkan'):
    print(f'== {y}')
    for k in KOL:
        v = [m[k, y, t] for t in (0, 1, 2) if m[k, y, t]]
        if v:
            print(f'{k:6s} ' + '  '.join(f'{a} {ozet([x[a] for x in v]) if len(v) > 1 else round(v[0][a], 1)}'
                                         for a in ('basari', 'guvensiz', 'sure', 'yumusak')))
if not all(m['D1', y, t] for y in ('rl', 'rl_kalkan') for t in (0, 1, 2)):
    print('D1 tamamlanmadi; karar yok')
else:
    ort = lambda k, y, a: st.mean(m[k, y, t][a] for t in (0, 1, 2))  # noqa: E731
    a_t = [m['D1', 'rl', t]['basari'] >= m['kiyas', 'rl', t]['basari'] + 5 for t in (0, 1, 2)]
    b_t = [m['D1', 'rl_kalkan', t]['basari'] >= m['kiyas', 'rl_kalkan', t]['basari'] + 5 for t in (0, 1, 2)]
    c_t = [m['D1', 'rl', t]['guvensiz'] <= m['kiyas', 'rl', t]['guvensiz'] + 5 for t in (0, 1, 2)]
    h_a = ort('D1', 'rl', 'basari') >= ort('kiyas', 'rl', 'basari') + 5
    h_b = ort('D1', 'rl_kalkan', 'basari') >= ort('kiyas', 'rl_kalkan', 'basari') + 5
    h_c = ort('D1', 'rl', 'guvensiz') <= ort('kiyas', 'rl', 'guvensiz') + 5
    print(f'H12a ortalama {h_a}, tohum {a_t} | H12b ortalama {h_b}, tohum {b_t} | H12c ortalama {h_c}, tohum {c_t}')
    ok = h_a and h_c and sum(a_t) >= 2 and sum(c_t) >= 2
    print(f'KARAR: egitimde 30 s {"benimsenir" if ok else "benimsenmez"} (paper %87.6 yalniz yan yana; kural farkli)')
