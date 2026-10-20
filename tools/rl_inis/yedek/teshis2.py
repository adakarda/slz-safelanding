"""Duzeltme 21 teshisi, ikinci kisim (tanimlayici): kalan sure asimlarinin son 10 s'si. Arac guvenli zeminin ~1-3 m
yanindayken neden ustune gecemiyor? Salinim mi (yol uzun, net yer degistirme kisa), egim mi (goruntunun merkezi
aracin altini gostermiyor)?

    $RL_PY teshis2.py MODEL.zip YEDEK.csv [--diag] [--shield-train-m 10] [--reward zemin_v3]
"""
import argparse
import csv
import math
import os
import statistics as st

import numpy as np
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv, lateral_index
from eland_rl.pilots import centre_safe, shield
from eland_rl.scenes import load_list
from eland_rl.yedek import yedek

ap = argparse.ArgumentParser()
ap.add_argument('model')
ap.add_argument('yedek_csv')
ap.add_argument('--diag', action='store_true')
ap.add_argument('--shield-train-m', type=float, default=-1.0)
ap.add_argument('--reward', default='zemin_v1')
a = ap.parse_args()

scenes = load_list(os.path.expanduser('~/eland_veri/rl/messi_ds4/val_b32.txt'), dist_cell_m=0.25)
idx = {sc.name: i for i, sc in enumerate(scenes)}
cfg = EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', shield_m=a.shield_train_m,
                diag_actions=a.diag, **REWARD_PRESETS[a.reward])
env = LandingEnv(scenes, cfg)
model = PPO.load(a.model, device='cpu')
to = [(r['scene'], int(r['start'])) for r in csv.DictReader(open(a.yedek_csv))
      if r['method'] == 'rl_kalkan_yedek' and r['outcome'] == 'timeout']

oran, donus, alt_gercek, merkez, ayni_yon, egim = [], [], [], [], [], []
for sc, k in to:
    obs, info = env.reset(seed=k, options={'scene_index': idx[sc]})
    iz = []
    while True:
        h = env.veh.delayed_pose()[0][2]
        p = int(model.predict(obs, deterministic=True)[0])
        act = shield(yedek(p, obs, h, env.veh.t, cfg.max_t, a.diag)[0], obs, h, 10.0)[0]
        x, y = env.veh.pos[0], env.veh.pos[1]
        gercek = env.scene.is_target(x, y, cfg.buffer_classes, cfg.buffer_m)
        R = env.veh.attitude()
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(-R[2, 2]) if R[2, 2] < 0 else float(R[2, 2])))))
        iz.append((env.veh.t, x, y, act, centre_safe(obs), bool(gercek), tilt))
        obs, r, done, trunc, info = env.step(act)
        if done or trunc:
            break
    son = [z for z in iz if z[0] >= 20.0]
    xy = np.array([(z[1], z[2]) for z in son])
    yol = float(np.sum(np.hypot(*np.diff(xy, axis=0).T)))
    net = float(np.hypot(*(xy[-1] - xy[0])))
    oran.append(net / yol if yol > 0 else float('nan'))
    yanal = [lateral_index(z[3]) for z in son if 1 <= z[3] <= 8 or z[3] >= 10]
    donus.append(sum(abs(((b - c + 4) % 8) - 4) >= 3 for b, c in zip(yanal, yanal[1:])))     # ~opposite direction
    alt_gercek.append(np.mean([z[5] for z in son]))
    merkez.append(np.mean([z[4] for z in son]))
    egim.append(np.median([z[6] for z in son]))

n = len(to)
print(f'{os.path.basename(os.path.dirname(a.model))}: {n} sure asimi, son 10 s')
print(f'  net yer degistirme / yol: medyan {st.median(oran):.2f} (1 = duz gidis, 0 = yerinde salinim)')
print(f'  ters yone donus sayisi: medyan {st.median(donus):.0f} (40 adimda)')
print(f'  aracin altindaki GERCEK nokta hedef: adim payi medyan {st.median(alt_gercek):.2f}; '
      f'> 0.2 olan deneme {sum(v > 0.2 for v in alt_gercek)}/{n}')
print(f'  goruntunun merkezi guvenli: adim payi medyan {st.median(merkez):.2f}')
print(f'  egim (derece): medyan {st.median(egim):.1f}')
