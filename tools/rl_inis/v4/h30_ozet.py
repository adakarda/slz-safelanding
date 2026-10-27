"""Duzeltme 30 ozeti: kaynak basina egitim (yalniz MESSI, yalniz FloodNet) ile birlesik egitim (v4_da), hepsi Depth
Anything. Kaynak basina (FloodNet, MESSI dogrulama) basari, sure ve guvensiz; segmentasyon {gt, v4}, kilitli kalkan.
  H30: birlesik, iki kaynakta da tek kaynakli kollarin en iyisinden en cok 2 puan dusukse "birlestirme zarar vermiyor";
       kendi kaynagi disinda tek kaynakli kol birlesikten 5 puandan fazla dusukse "birlestirme genellemeyi artiriyor".

    python3 h30_ozet.py
"""
import csv
import glob
import os
import statistics as st

D = os.path.expanduser('~/rl_inis/kos/v4/faktor')
GRUP = {'yalniz_messi': 'yalnız MESSI (365)', 'yalniz_flood': 'yalnız FloodNet (365)', 'yeni_da': 'birleşik (730)'}


def olc(p, seg, kaynak):
    rs = [r for r in csv.DictReader(open(p)) if r['seg'] == seg and r['kalkan'] == 'kilitli' and r['kaynak'] == kaynak]
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    u = sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs)
    return 100 * len(ok) / len(rs), st.mean(ok) if ok else 30.0, 100 * u / len(rs)


m = {}
for g, ad in GRUP.items():
    ps = sorted(glob.glob(f'{D}/{g}_s*.csv'))
    if not ps:
        continue
    for seg in ('gt', 'v4'):
        for kaynak in ('floodnet', 'messi'):
            v = [olc(p, seg, kaynak) for p in ps]
            m[(g, seg, kaynak)] = tuple(st.mean(x[i] for x in v) for i in range(3))
            print(f'{ad:22s} {seg} {kaynak:8s} basari %{m[(g, seg, kaynak)][0]:5.1f} '
                  f'{[round(x[0], 1) for x in v]} sure {m[(g, seg, kaynak)][1]:5.2f} s guvensiz %{m[(g, seg, kaynak)][2]:4.1f}')
if all((g, 'v4', k) in m for g in GRUP for k in ('floodnet', 'messi')):
    zarar_yok = all(m[('yeni_da', 'v4', k)][0] >= max(m[('yalniz_messi', 'v4', k)][0], m[('yalniz_flood', 'v4', k)][0]) - 2
                    for k in ('floodnet', 'messi'))
    genel = (m[('yalniz_messi', 'v4', 'floodnet')][0] < m[('yeni_da', 'v4', 'floodnet')][0] - 5
             or m[('yalniz_flood', 'v4', 'messi')][0] < m[('yeni_da', 'v4', 'messi')][0] - 5)
    print(f'H30: birlestirme zarar vermiyor {zarar_yok} | birlestirme genellemeyi artiriyor {genel}')
