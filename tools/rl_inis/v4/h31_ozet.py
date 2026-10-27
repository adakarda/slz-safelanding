"""Duzeltme 31 ozeti: hepsi_da (MESSI + FloodNet + VDD, 1010 sahne, 5 tohum) ile yeni_da (MESSI + FloodNet, 730, 5 tohum),
v4 dogrulama (175 sahne), kilitli kalkan. H31: hepsi_da (v4 segmentasyonu) basari >= yeni_da - 1 ve guvensiz <= yeni_da + 1
ise "VDD eklemek zarar vermiyor"; basari >= yeni_da + 2 ise "VDD eklemek iyilestiriyor".

    python3 h31_ozet.py
"""
import csv, glob, os, statistics as st
D = os.path.expanduser('~/rl_inis/kos/v4/faktor')
def olc(p, seg, kaynak=None):
    rs = [r for r in csv.DictReader(open(p)) if r['seg'] == seg and r['kalkan'] == 'kilitli' and (kaynak is None or r['kaynak'] == kaynak)]
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return 100 * len(ok) / len(rs), st.mean(ok), 100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / len(rs)
m = {}
for g in ('yeni_da', 'hepsi_da'):
    ps = sorted(glob.glob(f'{D}/{g}_s*.csv'))
    for seg in ('gt', 'v3', 'v4'):
        for k in (None, 'floodnet', 'messi'):
            v = [olc(p, seg, k) for p in ps]
            m[(g, seg, k)] = tuple(st.mean(x[i] for x in v) for i in range(3))
            print(f'{g:9s} {seg} {k or "hepsi":8s} basari %{m[(g, seg, k)][0]:5.1f} {[round(x[0], 1) for x in v]} sure {m[(g, seg, k)][1]:5.2f} s guvensiz %{m[(g, seg, k)][2]:4.1f}')
y, h = m[('yeni_da', 'v4', None)], m[('hepsi_da', 'v4', None)]
print(f'H31: VDD eklemek zarar vermiyor {h[0] >= y[0] - 1 and h[2] <= y[2] + 1} | iyilestiriyor {h[0] >= y[0] + 2}')
