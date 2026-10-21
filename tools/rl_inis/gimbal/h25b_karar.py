"""Duzeltme 25b, H25b karar kurali (on kayitli): gimbal'la egitilen c23 tarifi (3 tohum), 25a'daki c23'un gimbal'la
degerlendirmesiyle (yontem rl_kalkan2, 3 tohum ortalamasi).

  basari >= kiyas + 3, ya da (sure <= kiyas - 1.0 s ve basari >= kiyas - 1); ve guvensiz <= kiyas + 2.

    python3 h25b_karar.py
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
           ('t2_c23_b1_adim05_alcal1', 't3_c23_b1_adim05_alcal1_s1', 't3_c23_b1_adim05_alcal1_s2')]
yeni_p = [f'{K}/hiz2/g_s{t}/eval_val_b32_10.csv' for t in (0, 1, 2)]
if not all(os.path.exists(p) for p in kiyas_p + yeni_p):
    print('KARAR: degerlendirmeler eksik')
    raise SystemExit
for yontem in ('rl', 'rl_kalkan', 'rl_kalkan2'):
    a = [olc(p, yontem) for p in kiyas_p]
    b = [olc(p, yontem) for p in yeni_p]
    print(f'{yontem:11s} c23 gimbal degerlendirme -> gimbal egitim: basari {st.mean(x["B"] for x in a):5.1f} -> '
          f'{st.mean(x["B"] for x in b):5.1f} {[round(x["B"], 1) for x in b]} | sure {st.mean(x["T"] for x in a):5.1f} -> '
          f'{st.mean(x["T"] for x in b):5.1f} s | guvensiz {st.mean(x["U"] for x in a):4.1f} -> {st.mean(x["U"] for x in b):4.1f}')
a = [olc(p) for p in kiyas_p]
b = [olc(p) for p in yeni_p]
B0, B1 = st.mean(x['B'] for x in a), st.mean(x['B'] for x in b)
T0, T1 = st.mean(x['T'] for x in a), st.mean(x['T'] for x in b)
U0, U1 = st.mean(x['U'] for x in a), st.mean(x['U'] for x in b)
ok = (B1 >= B0 + 3 or (T1 <= T0 - 1.0 and B1 >= B0 - 1)) and U1 <= U0 + 2
print('KARAR: gimbal\'la egitim ' + ('benimsenir' if ok else 'benimsenmez'))
