"""Duzeltme 11 karar kurali (on kayitli): C1 (zemin_v2) ile B1 (zemin_v1), ayni tohumlar, val_b32 (320 deneme / kosu).

    python3 h11_karar.py

yumusak = yumusak zemine basarili inis (soft=1; 2 m icinde insan/arac yok) / 320; basari = zemin_success / 320;
guvensiz = indi ama zemin_success degil / 320. Birincil: kalkansiz RL.
H11a: C1 yumusak >= B1 yumusak + 10 puan | H11b: C1 basari >= B1 basari - 5 puan |
H11c: C1 guvensiz <= B1 guvensiz + 5 puan.
Karar: uc tahmin de ortalamada saglanir ve her biri tohum ciftlerinin (C1-sN / B1-sN) en az 2'sinde saglanirsa
zemin_v2 benimsenir. Sert, sure doldu ve SORA 3 m tanimlayici; karara girmez.
"""
import csv
import os
import statistics as st

K = os.path.expanduser('~/rl_inis/kos')
KOL = {'B1': 'b_B1_s{}', 'C1': 'c_C1_s{}'}


def olc(kol, tohum, yontem='rl'):
    f = os.path.join(K, KOL[kol].format(tohum), 'eval_val.csv')
    if not os.path.exists(f):
        return None
    rs = [r for r in csv.DictReader(open(f)) if r['method'] == yontem]
    n = len(rs)
    pay = lambda k: 100 * sum(k(r) for r in rs) / n  # noqa: E731
    return {'yumusak': pay(lambda r: r['soft'] == '1'),
            'basari': pay(lambda r: r['zemin_success'] == '1'),
            'guvensiz': pay(lambda r: r['outcome'] in ('safe_landing', 'unsafe_landing') and r['zemin_success'] != '1'),
            'sert': pay(lambda r: r['zemin_success'] == '1' and r['soft'] != '1'),
            'sure': pay(lambda r: r['outcome'] == 'timeout'),
            'sora': pay(lambda r: r['sora_success'] == '1')}


def ozet(v):
    return f'{st.mean(v):5.1f} ± {st.stdev(v):4.1f}' if len(v) > 1 else (f'{v[0]:5.1f}' if v else '  -  ')


OLCUT = ('yumusak', 'basari', 'guvensiz', 'sert', 'sure', 'sora')
for yontem in ('rl', 'rl_kalkan'):
    print(f'== {yontem} (val_b32, 320 deneme / kosu)')
    m = {(k, t): olc(k, t, yontem) for k in KOL for t in (0, 1, 2)}
    print(f'{"kol":4s} ' + ' '.join(f'{a:>14s}' for a in OLCUT))
    for k in KOL:
        print(f'{k:4s} ' + ' '.join(f'{ozet([m[k, t][a] for t in (0, 1, 2) if m[k, t]]):>14s}' for a in OLCUT))
        for t in (0, 1, 2):
            if m[k, t]:
                print(f'  s{t}  ' + ' '.join(f'{m[k, t][a]:14.1f}' for a in OLCUT))
    if yontem != 'rl':
        continue
    if not all(m['C1', t] for t in (0, 1, 2)):
        print('C1 tamamlanmadi; karar yok')
        continue
    ort = lambda k, a: st.mean(m[k, t][a] for t in (0, 1, 2))  # noqa: E731
    a_t = [m['C1', t]['yumusak'] >= m['B1', t]['yumusak'] + 10 for t in (0, 1, 2)]
    b_t = [m['C1', t]['basari'] >= m['B1', t]['basari'] - 5 for t in (0, 1, 2)]
    c_t = [m['C1', t]['guvensiz'] <= m['B1', t]['guvensiz'] + 5 for t in (0, 1, 2)]
    h11a = ort('C1', 'yumusak') >= ort('B1', 'yumusak') + 10
    h11b = ort('C1', 'basari') >= ort('B1', 'basari') - 5
    h11c = ort('C1', 'guvensiz') <= ort('B1', 'guvensiz') + 5
    print(f'H11a ortalama {h11a}, tohum {a_t} | H11b ortalama {h11b}, tohum {b_t} | H11c ortalama {h11c}, tohum {c_t}')
    ok = h11a and h11b and h11c and sum(a_t) >= 2 and sum(b_t) >= 2 and sum(c_t) >= 2
    print(f'KARAR: zemin_v2 {"benimsenir" if ok else "benimsenmez"}')
    # AirSim'e gidecek model (airsim_faz6_onkayit.md): H11b ve H11c'yi kendi tohum ciftinde saglayanlar icinde
    # yumusak orani en yuksek olan; hicbiri saglamazsa (ya da benimsenmezse) tanimlayici kiyas icin yumusak en yuksek
    aday = [t for t in (0, 1, 2) if b_t[t] and c_t[t]] or [0, 1, 2]
    en = max(aday, key=lambda t: m['C1', t]['yumusak'])
    print(f'AirSim modeli: C1-s{en} ({"benimsendi" if ok else "tanimlayici"}; '
          f'yumusak {m["C1", en]["yumusak"]:.1f}, basari {m["C1", en]["basari"]:.1f})')
