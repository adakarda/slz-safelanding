"""Duzeltme 21 teshisi (tanimlayici, karar degistirmez): yedek inise ragmen sure asimi kalan denemelerde arac nerede,
ne goruyor, ne yapiyor? Ayni baslangiclar yeniden kosulur (deterministik), her adim kaydedilir.

    $RL_PY teshis.py MODEL.zip YEDEK.csv [--diag] [--shield-train-m 10] [--reward zemin_v3]
"""
import argparse
import collections
import csv
import os
import statistics as st

import cv2
import numpy as np
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.pilots import centre_safe, shield
from eland_rl.scenes import load_list
from eland_rl.yedek import gerekli_sure, yedek

ap = argparse.ArgumentParser()
ap.add_argument('model')
ap.add_argument('yedek_csv')
ap.add_argument('--diag', action='store_true')
ap.add_argument('--shield-train-m', type=float, default=-1.0)
ap.add_argument('--reward', default='zemin_v1')
a = ap.parse_args()

scenes = load_list(os.path.expanduser('~/eland_veri/rl/messi_ds4/val_b32.txt'), dist_cell_m=0.25)
idx = {sc.name: i for i, sc in enumerate(scenes)}
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                   shield_m=a.shield_train_m, diag_actions=a.diag, **REWARD_PRESETS[a.reward]))
model = PPO.load(a.model, device='cpu')
to = [(r['scene'], int(r['start'])) for r in csv.DictReader(open(a.yedek_csv))
      if r['method'] == 'rl_kalkan_yedek' and r['outcome'] == 'timeout']

sigan_yok_son10, en_yakin_iz = [], []
son_h, gorus_yok_son10, merkez_guvenli_son10, eylem_son10, tetik_t, ilk_gorus_yok_h = [], [], [], collections.Counter(), [], []
for sc, k in to:
    obs, info = env.reset(seed=k, options={'scene_index': idx[sc]})
    kayit, tetik = [], None
    while True:
        h = env.veh.delayed_pose()[0][2]
        p = int(model.predict(obs, deterministic=True)[0])
        y, m = yedek(p, obs, h, env.veh.t, env.cfg.max_t, a.diag)
        act = shield(y, obs, h, 10.0)[0]
        if tetik is None and env.cfg.max_t - env.veh.t <= gerekli_sure(h):
            tetik = env.veh.t
        g = (obs[2] > 0.5).astype(np.uint8)
        sigan = cv2.erode(g, np.ones((4, 4), np.uint8))   # pixels where the 4x4 centre block would fit
        ys, xs = np.nonzero(g)
        dmin = float(np.min(np.hypot(xs - 63.5, (ys - 63.5) * 0.75))) if len(ys) else float('nan')
        kayit.append((env.veh.t, h, bool(g.any()), centre_safe(obs), act, bool(sigan.any()), dmin))
        obs, r, done, trunc, info = env.step(act)
        if done or trunc:
            break
    assert info['outcome'] == 'timeout', (sc, k, info['outcome'])
    son = [x for x in kayit if x[0] >= 20.0]
    son_h.append(kayit[-1][1])
    sigan_yok_son10.append(np.mean([x[2] and not x[5] for x in son]))
    en_yakin_iz.append([x[6] for x in son])
    gorus_yok_son10.append(np.mean([not x[2] for x in son]))
    merkez_guvenli_son10.append(np.mean([x[3] for x in son]))
    eylem_son10.update('dur' if x[4] == 0 else 'alcal' if x[4] == 9 else 'kay+alcal' if x[4] >= 10 else 'kay' for x in son)
    tetik_t.append(tetik if tetik is not None else float('nan'))
    gy = [x[1] for x in kayit if not x[2]]
    ilk_gorus_yok_h.append(gy[0] if gy else float('nan'))

n = len(to)
print(f'{os.path.basename(os.path.dirname(a.model))}: yedege ragmen sure asimi {n}')
print(f'  bitiste yukseklik: medyan {st.median(son_h):.1f} m, en az {min(son_h):.1f}, en cok {max(son_h):.1f}; '
      f'< 10 m olan {sum(h < 10 for h in son_h)}/{n}')
print(f'  son 10 s: gorusde hic guvenli piksel yok (adim payi) medyan {st.median(gorus_yok_son10):.2f}; '
      f'butun son 10 s boyunca yok {sum(g > 0.99 for g in gorus_yok_son10)}/{n}')
print(f'  son 10 s: merkez guvenli payi medyan {st.median(merkez_guvenli_son10):.2f}')
tot = sum(eylem_son10.values())
print('  son 10 s eylemleri: ' + ', '.join(f'{k} {v / tot:.2f}' for k, v in eylem_son10.most_common()))
tt = [t for t in tetik_t if t == t]
print(f'  yedegin tetiklendigi an: medyan {st.median(tt):.1f} s ({len(tt)}/{n} denemede)')
gy = [h for h in ilk_gorus_yok_h if h == h]
print(f'  gorusun ilk kez bos kaldigi yukseklik: medyan {st.median(gy):.1f} m ({len(gy)}/{n} denemede)' if gy else
      '  gorus hic bos kalmadi')
print(f'  son 10 s: guvenli piksel var ama 4x4 merkez blogu hicbir yere sigmiyor (adim payi) medyan '
      f'{st.median(sigan_yok_son10):.2f}; payi > 0.5 olan deneme {sum(v > 0.5 for v in sigan_yok_son10)}/{n}')
dd = [np.nanmedian(z) for z in en_yakin_iz if len(z)]
print(f'  son 10 s: en yakin guvenli piksele uzaklik medyan {np.nanmedian(dd):.1f} piksel '
      f'(8.8 m irtifada 1 piksel ~0.16 m)')
