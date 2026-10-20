"""Duzeltme 14 karar kurali (on kayitli): F1 (zemin_v3 + egitimde 30 s) ile B1, ayni tohumlar; D1 tanimlayici.

    python3 h14_karar.py

H14a: F1 basari >= B1 - 3 | H14b: F1 basarili inis suresi <= B1 - 2 s | H14c: F1 guvensiz <= B1 + 5.
Karar: uc tahmin de ortalamada ve tohum ciftlerinin en az 2'sinde saglanirsa zemin_v3 + egitimde 30 s benimsenir.
"""
import csv
import os
import statistics as st

K = os.path.expanduser('~/rl_inis/kos')
KOL = {'B1': 'b_B1_s{}', 'D1': 'd_D1_s{}', 'F1': 'f_F1_s{}'}


def olc(kol, t, yontem='rl'):
    f = os.path.join(K, KOL[kol].format(t), 'eval_val.csv')
    if not os.path.exists(f):
        return None
    rs = [r for r in csv.DictReader(open(f)) if r['method'] == yontem]
    n = len(rs)
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return {'basari': 100 * len(ok) / n, 'sure': st.mean(ok) if ok else float('nan'),
            'guvensiz': 100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / n,
            'sure_doldu': 100 * sum(r['outcome'] == 'timeout' for r in rs) / n,
            'yumusak': 100 * sum(r['soft'] == '1' for r in rs) / n}


OL = ('basari', 'sure', 'guvensiz', 'sure_doldu', 'yumusak')
for y in ('rl', 'rl_kalkan'):
    print(f'== {y} (paper: %87.6, 11.8 s; kural farkli)')
    print('kol   ' + ' '.join(f'{a:>14s}' for a in OL))
    for k in KOL:
        v = [m for m in (olc(k, t, y) for t in (0, 1, 2)) if m]
        if v:
            print(f'{k:5s} ' + ' '.join(f'{st.mean(x[a] for x in v):8.1f} ± {st.stdev(x[a] for x in v) if len(v) > 1 else 0:4.1f}'
                                        for a in OL))
m = {(k, t): olc(k, t) for k in ('B1', 'F1') for t in (0, 1, 2)}
if not all(m.values()):
    print('F1 tamamlanmadi; karar yok')
else:
    ort = lambda k, a: st.mean(m[k, t][a] for t in (0, 1, 2))  # noqa: E731
    a_t = [m['F1', t]['basari'] >= m['B1', t]['basari'] - 3 for t in (0, 1, 2)]
    b_t = [m['F1', t]['sure'] <= m['B1', t]['sure'] - 2 for t in (0, 1, 2)]
    c_t = [m['F1', t]['guvensiz'] <= m['B1', t]['guvensiz'] + 5 for t in (0, 1, 2)]
    h_a = ort('F1', 'basari') >= ort('B1', 'basari') - 3
    h_b = ort('F1', 'sure') <= ort('B1', 'sure') - 2
    h_c = ort('F1', 'guvensiz') <= ort('B1', 'guvensiz') + 5
    print(f'H14a ortalama {h_a}, tohum {a_t} | H14b ortalama {h_b}, tohum {b_t} | H14c ortalama {h_c}, tohum {c_t}')
    ok = h_a and h_b and h_c and sum(a_t) >= 2 and sum(b_t) >= 2 and sum(c_t) >= 2
    print(f'KARAR: zemin_v3 + egitimde 30 s {"benimsenir" if ok else "benimsenmez"}')
