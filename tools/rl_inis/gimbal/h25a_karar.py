"""Duzeltme 25a, H25a karar kurali (on kayitli): ortamda gimbal (egitim yok), ayni modellerin gimbalsiz sonuclariyla esli.

  c13 ve c23 icin ayri ayri, 3 tohum ortalamasi, yontem rl_kalkan2:
    basari >= gimbalsiz - 1, ve (sure <= gimbalsiz - 1.0 s ya da basari >= gimbalsiz + 3), ve guvensiz <= gimbalsiz + 2.
  Ikisinde de tutarsa gimbal benimsenir. Tanimlayici: rl ve rl_kalkan da.

    python3 h25a_karar.py
"""
import csv
import os
import statistics as st

H = os.path.expanduser('~')
K = f'{H}/rl_inis/kos'
G = f'{K}/gimbal_deger'
AYARLAR = {
    'c13': ['arama/t2_c13_f_kayarak_kalkan', 'arama/t3_c13_f_kayarak_kalkan_s1', 'arama/t3_c13_f_kayarak_kalkan_s2'],
    'c23': ['arama/t2_c23_b1_adim05_alcal1', 'arama/t3_c23_b1_adim05_alcal1_s1', 'arama/t3_c23_b1_adim05_alcal1_s2'],
    'B2': ['b_B2_s0'],
}


def olc(p, yontem):
    rs = [r for r in csv.DictReader(open(p)) if r['method'] == yontem]
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return dict(B=100 * len(ok) / len(rs), T=st.mean(ok) if ok else 30.0,
                U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / len(rs))


def gimbalsiz(d, yontem):
    if yontem == 'rl_kalkan2':
        return olc(f'{K}/kalkan2/{os.path.basename(d)}.csv', 'rl_kalkan2')
    p = f'{K}/{d}/eval_val_b32_10.csv'
    return olc(p if os.path.exists(p) else f'{K}/{d}/eval_val.csv', yontem)


kabul = {}
for ayar, dizinler in AYARLAR.items():
    print(f'== {ayar}')
    ozet = {}
    for yontem in ('rl', 'rl_kalkan', 'rl_kalkan2'):
        a, b = [], []
        for d in dizinler:
            p = f'{G}/{os.path.basename(d)}.csv'
            if not os.path.exists(p):
                continue
            a.append(gimbalsiz(d, yontem))
            b.append(olc(p, yontem))
        if not b:
            print('  degerlendirme yok')
            break
        m = {k: (st.mean(x[k] for x in a), st.mean(x[k] for x in b)) for k in ('B', 'T', 'U')}
        ozet[yontem] = (m, len(b))
        print(f'  {yontem:11s} basari {m["B"][0]:5.1f} -> {m["B"][1]:5.1f} | sure {m["T"][0]:5.1f} -> {m["T"][1]:5.1f} s | '
              f'guvensiz {m["U"][0]:4.1f} -> {m["U"][1]:4.1f}  ({len(b)} model)')
    if ayar == 'B2' or 'rl_kalkan2' not in ozet or ozet['rl_kalkan2'][1] < 3:
        continue
    m = ozet['rl_kalkan2'][0]
    h1 = m['B'][1] >= m['B'][0] - 1
    h2 = m['T'][1] <= m['T'][0] - 1.0 or m['B'][1] >= m['B'][0] + 3
    h3 = m['U'][1] <= m['U'][0] + 2
    kabul[ayar] = h1 and h2 and h3
    print(f'  H25a: basari tutuyor {h1} | hiz ya da basari kazanci {h2} | guvensiz {h3}')
print('KARAR: ' + ('degerlendirmeler eksik' if len(kabul) < 2 else
                   'gimbal ' + ('benimsenir' if all(kabul.values()) else 'benimsenmez') + f' {kabul}'))
