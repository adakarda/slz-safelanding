"""Duzeltme 29 ozeti ve kararlar. Grup = ajan (veri x derinlik), tohumlarin ortalamasi; hucre = segmentasyon x kalkan.
  H29a (segmentasyon): c13 + kilitli kalkanla v4 maskesindeki basari >= v3 maskesindeki + 3 ise "v4 segmentasyonu
        RL icin daha iyi".
  H29b (kalkan): her grupta ve her segmentasyonda kilitli >= eski >= yok mu (tanimlayici sayim).
  H29c (veri x derinlik, v4 segmentasyonu + kilitli kalkan, en iyi grup): tanimlayici.
Cikti ayrica ~/rl_inis/kos/v4/faktor/ozet.csv.

    python3 h29_ozet.py
"""
import collections
import csv
import glob
import os
import statistics as st

D = os.path.expanduser('~/rl_inis/kos/v4/faktor')
GRUP = {'eski_c13': 'eski veri + irtifa (c13)', 'eski_da': 'eski veri + Depth Anything',
        'yeni_irtifa': 'yeni veri + irtifa', 'yeni_da': 'yeni veri + Depth Anything'}

tablo = collections.defaultdict(list)          # (grup, seg, kalkan) -> per-seed (B, T, U)
for p in sorted(glob.glob(f'{D}/*.csv')):
    ad = os.path.basename(p)[:-4]
    g = ad.rsplit('_s', 1)[0]
    if g not in GRUP:
        continue
    rs = list(csv.DictReader(open(p)))
    for seg in ('gt', 'v3', 'v4'):
        for kalkan in ('yok', 'eski', 'kilitli'):
            r = [x for x in rs if x['seg'] == seg and x['kalkan'] == kalkan]
            ok = [float(x['t']) for x in r if x['zemin_success'] == '1']
            u = sum(x['outcome'] != 'timeout' and x['zemin_success'] != '1' for x in r)
            tablo[(g, seg, kalkan)].append((100 * len(ok) / len(r), st.mean(ok) if ok else 30.0, 100 * u / len(r)))
with open(f'{D}/ozet.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['grup', 'seg', 'kalkan', 'tohum', 'basari', 'sure_s', 'guvensiz', 'basari_tohumlar'])
    for (g, seg, kalkan), v in sorted(tablo.items()):
        w.writerow([g, seg, kalkan, len(v), round(st.mean(x[0] for x in v), 1), round(st.mean(x[1] for x in v), 2),
                    round(st.mean(x[2] for x in v), 1), ' '.join(f'{x[0]:.1f}' for x in v)])
for g in GRUP:
    print(f'== {GRUP[g]}')
    for seg in ('gt', 'v3', 'v4'):
        hucre = []
        for kalkan in ('yok', 'eski', 'kilitli'):
            v = tablo.get((g, seg, kalkan))
            if v:
                hucre.append(f'{kalkan} %{st.mean(x[0] for x in v):5.1f} {st.mean(x[1] for x in v):4.1f}s '
                             f'g%{st.mean(x[2] for x in v):4.1f}')
        print(f'   {seg:3s} | ' + ' | '.join(hucre))


def b(g, seg, kalkan):
    return st.mean(x[0] for x in tablo[(g, seg, kalkan)])


if tablo.get(('eski_c13', 'v4', 'kilitli')) and tablo.get(('eski_c13', 'v3', 'kilitli')):
    h29a = b('eski_c13', 'v4', 'kilitli') >= b('eski_c13', 'v3', 'kilitli') + 3
    print(f'H29a {h29a}: c13 + kilitli, v4 %{b("eski_c13", "v4", "kilitli"):.1f} / v3 %{b("eski_c13", "v3", "kilitli"):.1f}'
          f' -> ' + ('v4 segmentasyonu RL icin daha iyi' if h29a else 'belirgin fark yok'))
sira = sum(b(g, s, 'kilitli') >= b(g, s, 'eski') >= b(g, s, 'yok') for g in GRUP for s in ('gt', 'v3', 'v4')
           if tablo.get((g, s, 'yok')))
print(f'H29b: kilitli >= eski >= yok sirasi {sira} hucrede tuttu')
en = max((g for g in GRUP if tablo.get((g, 'v4', 'kilitli'))), key=lambda g: b(g, 'v4', 'kilitli'))
print(f'H29c: v4 segmentasyonu + kilitli kalkanla en iyi grup: {GRUP[en]} (%{b(en, "v4", "kilitli"):.1f})')
