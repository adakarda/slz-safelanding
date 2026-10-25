"""Duzeltme 28, H28 karar kurali (on kayitli). Yontem rl_kalkan2, v4 dogrulama sahneleri.
  H28a (yeni model eskiden iyi mi): v4_da 5 tohum ortalamasi, eski son aday c13 (3 tohum) ortalamasina karsi:
        (basari >= eski + 3 ya da (sure <= eski - 1.0 s ve basari >= eski - 1)) ve guvensiz <= eski + 2.
  H28b (kararlilik): v4_da'nin en kotu tohumu >= %80.
  Ikisi de tutarsa v4_da yeni son aday olur.
Tanimlayici: kaynak basina (FloodNet, MESSI), yalin RL, Duzeltme 27'nin C_da modelleri.

    python3 h28_karar.py
"""
import csv
import glob
import os
import statistics as st

D = os.path.expanduser('~/rl_inis/kos/v4/deger')


def olc(p, y, kaynak=None):
    rs = [r for r in csv.DictReader(open(p)) if r['method'] == y and (kaynak is None or r['kaynak'] == kaynak)]
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return dict(B=100 * len(ok) / len(rs), T=st.mean(ok) if ok else 30.0,
                U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / len(rs))


gruplar = {'v4_da': sorted(glob.glob(f'{D}/v4_da_s*.csv')), 'eski_c13': sorted(glob.glob(f'{D}/eski_c13_s*.csv')),
           'd27_C_da': sorted(glob.glob(f'{D}/d27_C_da_s*.csv'))}
if len(gruplar['v4_da']) < 5 or len(gruplar['eski_c13']) < 3:
    print('KARAR: degerlendirmeler eksik', {k: len(v) for k, v in gruplar.items()})
    raise SystemExit
m = {}
for y in ('rl', 'rl_kalkan2'):
    for kaynak in (None, 'floodnet', 'messi'):
        for g, ps in gruplar.items():
            if not ps:
                continue
            v = [olc(p, y, kaynak) for p in ps]
            ort = {x: st.mean(d[x] for d in v) for x in 'BTU'}
            m[(g, y, kaynak)] = (ort, v)
            print(f'{y:11s} {kaynak or "hepsi":8s} {g:9s} basari {ort["B"]:5.1f} {[round(d["B"], 1) for d in v]} | '
                  f'sure {ort["T"]:5.2f} s | guvensiz {ort["U"]:4.1f}')
yeni, yv = m[('v4_da', 'rl_kalkan2', None)]
eski, _ = m[('eski_c13', 'rl_kalkan2', None)]
h28a = ((yeni['B'] >= eski['B'] + 3 or (yeni['T'] <= eski['T'] - 1.0 and yeni['B'] >= eski['B'] - 1))
        and yeni['U'] <= eski['U'] + 2)
h28b = min(d['B'] for d in yv) >= 80
print(f'H28a {h28a} | H28b {h28b} (en kotu tohum {min(d["B"] for d in yv):.1f})')
print('KARAR: v4_da ' + ('yeni son aday' if h28a and h28b else 'son aday olmaz'))
