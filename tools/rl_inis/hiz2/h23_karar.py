"""Duzeltme 23, H23 karar kurali (on kayitli): RL modunda hizli son inis (--hizli-son 2), Faz 7'nin f7_rl_k10_gt koluyla
esli (ayni 30 havada baslangic, ayni model c23 s1, AirSim etiketi, kalkan 10).

  H23a  her iki kolda da inen esli kosularda inis suresi farkinin medyani <= -2.0 s
  H23b  temas hizi 1.0 m/s'yi asan inis sayisi kiyastan fazla degil
  H23c  zemin kuralina uygun inis (ortografik harita) kiyastan en cok 1 az
  Uc de tutarsa benimsenir.

    python3 h23_karar.py [KIYAS.harita.jsonl] [YENI.harita.jsonl]
"""
import json
import os
import statistics as st
import sys

F = os.path.expanduser('~/eland_veri/_gunlukler/airsim_faz3')
kiyas = sys.argv[1] if len(sys.argv) > 1 else f'{F}/f7_rl_k10_gt.jsonl.harita.jsonl'
yeni = sys.argv[2] if len(sys.argv) > 2 else f'{F}/f8_rl_k10_gt_hs2.jsonl.harita.jsonl'


def oku(p):
    return {r['kosu']: r for r in map(json.loads, open(p))}


a, b = oku(kiyas), oku(yeni)
ortak = sorted(k for k in a if k in b and a[k].get('sonuc') == 'indi' and b[k].get('sonuc') == 'indi')
fark = [b[k]['sure_s'] - a[k]['sure_s'] for k in ortak]


def ozet(d, ad):
    indi = [r for r in d.values() if r.get('sonuc') == 'indi']
    s = [r['sure_s'] for r in indi]
    v = [r['temas_hizi_mps'] for r in indi if r.get('temas_hizi_mps') is not None]
    print(f'{ad:10s} kosu {len(d)}, indi {len(indi)}, zemin uygun {sum(bool(r.get("zemin_uygun")) for r in indi)}, '
          f'SORA uygun {sum(bool(r.get("sora_uygun")) for r in indi)} | sure medyan {st.median(s):.1f} s, ort {st.mean(s):.1f} | '
          f'temas ort {st.mean(v):.2f}, en cok {max(v):.2f}, > 1.0: {sum(x > 1.0 for x in v)}')
    return indi, v


ia, va = ozet(a, 'kiyas')
ib, vb = ozet(b, 'hizli son')
print(f'esli inen {len(ortak)}: sure farki medyan {st.median(fark):+.1f} s, ort {st.mean(fark):+.1f} s')
h_a = st.median(fark) <= -2.0
h_b = sum(x > 1.0 for x in vb) <= sum(x > 1.0 for x in va)
h_c = sum(bool(r.get('zemin_uygun')) for r in ib) >= sum(bool(r.get('zemin_uygun')) for r in ia) - 1
print(f'H23a {h_a} | H23b {h_b} | H23c {h_c}')
print('KARAR: hizli son inis ' + ('benimsenir' if h_a and h_b and h_c else 'benimsenmez'))
