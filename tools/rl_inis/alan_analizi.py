"""Basarisizlik inilebilir alanin azligindan mi? (tanimlayici, karar yok)

    bash ~/rl_inis/py.sh alan_analizi.py [kos/b_B2_s0]

val_b32'nin 320 baslangici (reset(seed=k), degerlendirmeyle ayni) icin: baslangic noktasindan en yakin hedefe
(inilebilir, insan/araca >= 2 m) uzaklik ve sahnenin hedef alan payi. Kosunun eval_val.csv'sindeki RL, duz alcalma
ve gorus kahini sonuclari bu iki degiskene gore bolunur.
"""
import collections
import csv
import os
import sys

import numpy as np

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

kosu = sys.argv[1] if len(sys.argv) > 1 else 'kos/b_B2_s0'
scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                   **REWARD_PRESETS['zemin_v1']))
bas = {}
pay = {}
for i, sc in enumerate(scenes):
    hedef, _, _ = sc._target_grid((6, 5), 2.0)
    pay[sc.name] = float(hedef.mean())
    for k in range(10):
        env.reset(seed=k, options={'scene_index': i})
        p = env.veh.pos
        bas[(sc.name, k)] = (sc.nearest_target(p[0], p[1], (6, 5), 2.0)[2], p[2])
rs = list(csv.DictReader(open(os.path.join(kosu, 'eval_val.csv'))))
yontemler = ('rl', 'rl_kalkan', 'duz_inis', 'gorus_kahini')
sonuc = {(r['method'], r['scene'], int(r['start'])): r for r in rs if r['method'] in yontemler}

print(f'sahnelerin hedef alan payi: ortalama {100 * np.mean(list(pay.values())):.1f} %, '
      f'en az {100 * min(pay.values()):.1f} %, en cok {100 * max(pay.values()):.1f} %')
print('\n== baslangictan en yakin hedefe uzakliga gore zemin basarisi (%)')
kutular = [(0, 0.01, 'tam ustunde'), (0.01, 5, '0-5 m'), (5, 10, '5-10 m'), (10, 20, '10-20 m'), (20, 1e9, '> 20 m')]
print(f'{"uzaklik":12s} {"n":>4s} ' + ' '.join(f'{y:>13s}' for y in yontemler) + '   RL basarisizlik turu')
for lo, hi, ad in kutular:
    ks = [key for key, (d, h) in bas.items() if lo <= d < hi]
    if not ks:
        continue
    satir = [100 * np.mean([sonuc[(y, s, k)]['zemin_success'] == '1' for s, k in ks]) for y in yontemler]
    tur = collections.Counter(sonuc[('rl', s, k)]['outcome'] for s, k in ks if sonuc[('rl', s, k)]['zemin_success'] != '1')
    print(f'{ad:12s} {len(ks):4d} ' + ' '.join(f'{v:13.1f}' for v in satir) + f'   {dict(tur)}')
print('\n== sahnenin hedef alan payina gore (sahneler 4 esit gruba bolundu)')
sirali = sorted(pay, key=pay.get)
for g in range(4):
    grup = sirali[g * len(sirali) // 4:(g + 1) * len(sirali) // 4]
    ks = [(s, k) for s in grup for k in range(10)]
    satir = [100 * np.mean([sonuc[(y, s, k)]['zemin_success'] == '1' for s, k in ks]) for y in yontemler]
    print(f'pay {100 * pay[grup[0]]:4.1f}-{100 * pay[grup[-1]]:4.1f} %  n {len(ks):3d} ' + ' '.join(f'{v:13.1f}' for v in satir))
d_rl_ok = [bas[(s, k)][0] for (y, s, k), r in sonuc.items() if y == 'rl' and r['zemin_success'] == '1']
d_rl_no = [bas[(s, k)][0] for (y, s, k), r in sonuc.items() if y == 'rl' and r['zemin_success'] != '1']
print(f'\nen yakin hedefe medyan uzaklik: RL basarili {np.median(d_rl_ok):.1f} m, RL basarisiz {np.median(d_rl_no):.1f} m')
