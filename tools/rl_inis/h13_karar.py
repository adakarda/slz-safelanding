"""Duzeltme 13 karar kurali (on kayitli): E1 (kayarken alcal) ile D1, ayni tohumlar, val_b32 (320 deneme / kosu).

    python3 h13_karar.py

sure = zemin kuralina gore basarili bolumlerin ortalama suresi (s). Birincil: kalkansiz RL.
H13a: E1 sure <= D1 sure - 2 s | H13b: E1 basari >= D1 basari - 3 | H13c: E1 guvensiz <= D1 guvensiz + 5.
Karar: uc tahmin de ortalamada ve tohum ciftlerinin en az 2'sinde saglanirsa kayarken alcal benimsenir.
"""
import csv
import os
import statistics as st

K = os.path.expanduser('~/rl_inis/kos')
KOL = {'D1': 'd_D1_s{}', 'E1': 'e_E1_s{}'}


def olc(kol, t, yontem):
    f = os.path.join(K, KOL[kol].format(t), 'eval_val.csv')
    if not os.path.exists(f):
        return None
    rs = [r for r in csv.DictReader(open(f)) if r['method'] == yontem]
    n = len(rs)
    ok = [r for r in rs if r['zemin_success'] == '1']
    return {'sure': st.mean(float(r['t']) for r in ok) if ok else float('nan'),
            'basari': 100 * len(ok) / n,
            'guvensiz': 100 * sum(r['outcome'] in ('safe_landing', 'unsafe_landing') and r['zemin_success'] != '1'
                                  for r in rs) / n,
            'sure_doldu': 100 * sum(r['outcome'] == 'timeout' for r in rs) / n,
            'yumusak': 100 * sum(r['soft'] == '1' for r in rs) / n}


def ozet(v):
    return f'{st.mean(v):5.1f} ± {st.stdev(v):4.1f}' if len(v) > 1 else f'{v[0]:5.1f}'


OL = ('sure', 'basari', 'guvensiz', 'sure_doldu', 'yumusak')
m = {(k, y, t): olc(k, t, y) for k in KOL for y in ('rl', 'rl_kalkan') for t in (0, 1, 2)}
for y in ('rl', 'rl_kalkan'):
    print(f'== {y} (paper RL 11.8 s; duz alcalma ~10.5 s; kahin ~13.8 s)')
    print('kol   ' + ' '.join(f'{a:>14s}' for a in OL))
    for k in KOL:
        v = [m[k, y, t] for t in (0, 1, 2) if m[k, y, t]]
        if v:
            print(f'{k:5s} ' + ' '.join(f'{ozet([x[a] for x in v]):>14s}' for a in OL))
if not all(m[k, 'rl', t] for k in KOL for t in (0, 1, 2)):
    print('D1 ya da E1 tamamlanmadi; karar yok')
else:
    ort = lambda k, a: st.mean(m[k, 'rl', t][a] for t in (0, 1, 2))  # noqa: E731
    a_t = [m['E1', 'rl', t]['sure'] <= m['D1', 'rl', t]['sure'] - 2 for t in (0, 1, 2)]
    b_t = [m['E1', 'rl', t]['basari'] >= m['D1', 'rl', t]['basari'] - 3 for t in (0, 1, 2)]
    c_t = [m['E1', 'rl', t]['guvensiz'] <= m['D1', 'rl', t]['guvensiz'] + 5 for t in (0, 1, 2)]
    h_a = ort('E1', 'sure') <= ort('D1', 'sure') - 2
    h_b = ort('E1', 'basari') >= ort('D1', 'basari') - 3
    h_c = ort('E1', 'guvensiz') <= ort('D1', 'guvensiz') + 5
    print(f'H13a ortalama {h_a}, tohum {a_t} | H13b ortalama {h_b}, tohum {b_t} | H13c ortalama {h_c}, tohum {c_t}')
    ok = h_a and h_b and h_c and sum(a_t) >= 2 and sum(b_t) >= 2 and sum(c_t) >= 2
    print(f'KARAR: kayarken alcal {"benimsenir" if ok else "benimsenmez"}')
