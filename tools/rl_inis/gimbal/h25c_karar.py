"""Duzeltme 25c, H25c karar kurali (on kayitli): AirSim'de RL + gimbal, Faz 7'nin R-GT koluyla esli (30 havada baslangic).

  zemin kuralina uygun >= R-GT, SORA >= R-GT ve sure medyani <= R-GT + 1 s. Ucu tutarsa AirSim'de gimbal benimsenir.
  Tanimlayici: RL modu etkinken adim basina eylem degisimi ve ters donus (politika.csv, rl_mod.log'daki etkinlesmeden sonra).

    python3 h25c_karar.py
"""
import csv
import glob
import json
import os
import re
import statistics as st

H = os.path.expanduser('~')
F = f'{H}/eland_veri/_gunlukler/airsim_faz3'


def oku(p):
    return [json.loads(l) for l in open(p)]


def ozet(rs, ad):
    indi = [r for r in rs if r.get('sonuc') == 'indi']
    z = sum(bool(r.get('zemin_uygun')) for r in indi)
    s = sum(bool(r.get('sora_uygun')) for r in indi)
    med = st.median(r['sure_s'] for r in indi) if indi else float('nan')
    print(f'{ad:10s} kosu {len(rs)}, indi {len(indi)}, zemin uygun {z}, SORA uygun {s}, sure medyan {med:.1f} s')
    return z, s, med


def degisim(kok):
    """Action changes and reversals per step while RL Landing was active, over a batch's runs."""
    adim = deg = ters = 0
    for k in sorted(glob.glob(f'{kok}/k[0-9][0-9]')):
        t0 = None
        log = f'{k}/rl_mod.log'
        if os.path.exists(log):
            m = re.search(r'\[(\d{10}\.\d+)\] \[rl_landing_mode\]: RL Landing active', open(log).read())
            t0 = float(m.group(1)) if m else None
        p = f'{k}/politika.csv'
        if t0 is None or not os.path.exists(p):
            continue
        ey = [int(r['action']) for r in csv.DictReader(open(p)) if float(r['t_wall']) >= t0 and float(r['z_cam']) > 5.0]
        for a, b in zip(ey, ey[1:]):
            adim += 1
            deg += a != b
            ters += 1 <= a <= 8 and 1 <= b <= 8 and abs(((a - b + 4) % 8) - 4) >= 3
    return (deg / adim, ters / adim, adim) if adim else (float('nan'), float('nan'), 0)


za, sa, ma = ozet(oku(f'{F}/f7_rl_k10_gt.jsonl.harita.jsonl'), 'R-GT')
zb, sb, mb = ozet(oku(f'{F}/f9_rl_k10_gt_gimbal.jsonl.harita.jsonl'), 'R-GT+gimbal')
G = f'{H}/eland_veri/_gunlukler'
for ad, desen in (('R-GT', 'airsim_inis_f7_rl_k10_gt_*'), ('R-GT+gimbal', 'airsim_inis_f9_rl_k10_gt_gimbal_*')):
    kok = sorted(glob.glob(f'{G}/{desen}'))[-1]
    d, t, n = degisim(kok)
    print(f'{ad:10s} RL etkinken: eylem degisimi {d:.3f}/adim, ters donus {t:.3f}/adim ({n} adim)')
ok = zb >= za and sb >= sa and mb <= ma + 1.0
print(f'H25c: zemin {zb} >= {za}: {zb >= za} | SORA {sb} >= {sa}: {sb >= sa} | sure {mb:.1f} <= {ma + 1:.1f}: {mb <= ma + 1}')
print('KARAR: AirSim\'de gimbal ' + ('benimsenir' if ok else 'benimsenmez'))
