"""Tanimlayici (Arda'nin sorusu, 21.10): yalpalama kameranin egiminden mi geliyor? Gimbal (sabit, hep dik bakan kamera)
olsaydi komut degisimi, zikzak, basari ve sure ne olurdu? Egitim yok.

1. AirSim (Faz 7 RL kolu, c23 s1, AirSim etiketi): egim buyukken bir sonraki adimda eylem daha sik mi degisiyor?
2. Hafif ortam, ayni model, val_b32 x 10 (320 deneme), kalkan 10 m: kamera govdeyle egilir (egitimdeki gibi) ile
   gimbal (kamera yalniz yonu tutar, hep dik). Ayni baslangiclar.

    $RL_PY gimbal_teshis.py
"""
import csv
import glob
import math
import os
import statistics as st

import numpy as np
from stable_baselines3 import PPO

from eland_rl import camera, dynamics
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.pilots import shield
from eland_rl.scenes import load_list

H = os.path.expanduser('~')


def ters(b, c):
    return 1 <= b <= 8 and 1 <= c <= 8 and abs(((b - c + 4) % 8) - 4) >= 3


# 1. AirSim
K = sorted(glob.glob(f'{H}/eland_veri/_gunlukler/airsim_inis_f7_rl_k10_gt_*/'))[-1]
kova = {'egim < 3': [0, 0], '3-8': [0, 0], '> 8': [0, 0]}
for p in sorted(glob.glob(f'{K}k*/politika.csv')):
    rs = [r for r in csv.DictReader(open(p)) if float(r['z_cam']) > 5.0]
    for r0, r1 in zip(rs, rs[1:]):
        e = float(r0['tilt_deg'])
        k = 'egim < 3' if e < 3 else '3-8' if e <= 8 else '> 8'
        kova[k][0] += 1
        kova[k][1] += int(r0['action'] != r1['action'])
print('AirSim: egime gore bir sonraki adimda eylem degisimi')
for k, (n, d) in kova.items():
    print(f'  {k:9s} adim {n:5d}  degisim payi {d / max(n, 1):.2f}')

# 2. light environment, tilted camera vs gimbal
scenes = load_list(f'{H}/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
model = PPO.load(f'{H}/rl_inis/kos/arama/t3_c23_b1_adim05_alcal1_s1/model.zip', device='cpu')
asil = dynamics.Vehicle.delayed_pose


def gimbal(self):
    pos, _ = asil(self)
    return pos, camera.rotation((0.0, 0.0, 1.0), self.yaw)


for ad, poz in (('egik kamera', asil), ('gimbal', gimbal)):
    dynamics.Vehicle.delayed_pose = poz
    env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                       **REWARD_PRESETS['zemin_v1']))
    basari, sure, adim, degisim, tersd, to, guv = 0, [], 0, 0, 0, 0, 0
    for i in range(len(scenes)):
        for k in range(10):
            obs, _ = env.reset(seed=k, options={'scene_index': i})
            onceki = None
            while True:
                h = env.veh.delayed_pose()[0][2]
                a = shield(int(model.predict(obs, deterministic=True)[0]), obs, h, 10.0)[0]
                if onceki is not None:
                    degisim += int(a != onceki)
                    tersd += int(ters(onceki, a))
                onceki = a
                adim += 1
                obs, _, done, trunc, info = env.step(a)
                if done or trunc:
                    break
            if info['zemin_success']:
                basari += 1
                sure.append(info['t'])
            to += info['outcome'] == 'timeout'
            guv += info['outcome'] != 'timeout' and not info['zemin_success']
    n = len(scenes) * 10
    print(f'{ad:12s} basari {100 * basari / n:5.1f} % | sure ort {st.mean(sure):5.1f} s | guvensiz {100 * guv / n:4.1f} % | '
          f'sure asimi {100 * to / n:4.1f} % | eylem degisimi {degisim / adim:.3f}/adim | ters donus {tersd / adim:.3f}/adim')
dynamics.Vehicle.delayed_pose = asil
