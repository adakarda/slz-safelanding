"""Bir AirSim batch'inde politikanin kendi sectigi ilk yanal eylemin irtifasi (kalkan mudahalesi sayilmaz).

    python3 ilk_yanal.py BATCH_KLASORU

Her kNN/politika.csv icin, RL Landing'in devreye girdigi andan (kNN/rl_mod.log) sonra: 'alcal' (9) ve 'dur' (0)
disindaki ilk politika eyleminin kamera yuksekligi; hic yoksa '-'. Tanimlayici olcut (airsim_faz6_onkayit.md),
karara girmez.
"""
import csv
import glob
import os
import re
import statistics as st
import sys

irtifa = []
for f in sorted(glob.glob(os.path.join(sys.argv[1], 'k*', 'politika.csv'))):
    d = os.path.dirname(f)
    t0 = None
    log = os.path.join(d, 'rl_mod.log')
    if os.path.exists(log):
        m = re.search(r'\[(\d+\.\d+)\] \[rl_landing_mode\]: RL Landing active', open(log).read())
        t0 = float(m.group(1)) if m else None
    if t0 is None:
        print(f'{os.path.basename(d)}: RL Landing devreye girmedi')
        continue
    rs = [r for r in csv.DictReader(open(f)) if float(r['t_wall']) >= t0]
    ilk = next((float(r['z_cam']) for r in rs if r['action'] not in ('9', '0') and r.get('kalkan', '0') != '1'), None)
    irtifa.append(ilk)
    print(f'{os.path.basename(d)}: ilk yanal {"-" if ilk is None else f"{ilk:.1f} m"}')
var = [x for x in irtifa if x is not None]
print(f'{len(irtifa)} kosu; yanal yok {len(irtifa) - len(var)}; medyan {st.median(var):.1f} m' if var
      else f'{len(irtifa)} kosu; hic yanal eylem yok')
