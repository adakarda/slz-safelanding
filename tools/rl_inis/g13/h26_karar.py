"""Duzeltme 26, H26 karar kurali (on kayitli): c13 tarifiyle gimbal'li egitim (g13, 3 tohum), 25a'daki c13'un gimbal'la
degerlendirmesiyle (yontem rl_kalkan2, 3 tohum ortalamasi).

  (sure <= kiyas - 1.0 s ve basari >= kiyas - 1) ya da basari >= kiyas + 3; ve guvensiz <= kiyas + 2.

Tanimlayici: 25b'nin g modelleri (c23 tarifi + gimbal egitim) ayni tabloda.

    python3 h26_karar.py
"""
import csv
import os
import statistics as st

H = os.path.expanduser('~')
K = f'{H}/rl_inis/kos'


def olc(p, yontem='rl_kalkan2'):
    rs = [r for r in csv.DictReader(open(p)) if r['method'] == yontem]
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return dict(B=100 * len(ok) / len(rs), T=st.mean(ok) if ok else 30.0,
                U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / len(rs))


kiyas_p = [f'{K}/gimbal_deger/{d}.csv' for d in
           ('t2_c13_f_kayarak_kalkan', 't3_c13_f_kayarak_kalkan_s1', 't3_c13_f_kayarak_kalkan_s2')]
yeni_p = [f'{K}/g13/g13_s{t}/eval_val_b32_10.csv' for t in (0, 1, 2)]
g_p = [p for p in (f'{K}/hiz2/g_s{t}/eval_val_b32_10.csv' for t in (0, 1, 2)) if os.path.exists(p)]
if not all(os.path.exists(p) for p in kiyas_p + yeni_p):
    print('KARAR: degerlendirmeler eksik')
    raise SystemExit
for yontem in ('rl', 'rl_kalkan', 'rl_kalkan2'):
    for ad, ps in (('c13 gimbal degerlendirme', kiyas_p), ('g13 gimbal egitim', yeni_p), (f'g (25b, {len(g_p)} tohum)', g_p)):
        if not ps:
            continue
        v = [olc(p, yontem) for p in ps]
        print(f'{yontem:11s} {ad:26s} basari {st.mean(x["B"] for x in v):5.1f} {[round(x["B"], 1) for x in v]} | '
              f'sure {st.mean(x["T"] for x in v):5.1f} s | guvensiz {st.mean(x["U"] for x in v):4.1f}')
a = [olc(p) for p in kiyas_p]
b = [olc(p) for p in yeni_p]
B0, B1 = st.mean(x['B'] for x in a), st.mean(x['B'] for x in b)
T0, T1 = st.mean(x['T'] for x in a), st.mean(x['T'] for x in b)
U0, U1 = st.mean(x['U'] for x in a), st.mean(x['U'] for x in b)
ok = ((T1 <= T0 - 1.0 and B1 >= B0 - 1) or B1 >= B0 + 3) and U1 <= U0 + 2
print(f'H26: basari {B0:.1f} -> {B1:.1f}, sure {T0:.2f} -> {T1:.2f} s, guvensiz {U0:.2f} -> {U1:.2f}')
print('KARAR: c13 tarifiyle gimbal\'li egitim ' + ('benimsenir' if ok else 'benimsenmez'))
