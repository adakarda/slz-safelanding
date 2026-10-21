"""Tanimlayici (Arda'nin sorusu, 21.10): AirSim'de kamera egimi ve zikzak, egitim ortamindakiyle ayni mi?

AirSim: Faz 7'nin RL kolu (c23 s1, AirSim etiketi, kalkan 10), policy_node'un politika.csv'leri, RL'nin yonettigi
adimlar (kamera 5 m ustunde). Hafif ortam: ayni model, val_b32'nin ilk 64 denemesi (sahne basina 2 baslangic),
nominal dinamik, ayni olcutler.
  egim: kameranin dikeyden sapmasi (derece); zikzak: art arda iki yanal eylem arasinda ters yone (>= 135 derece)
  donus orani; yanal pay: yanal eylemlerin payi.

    $RL_PY egim_kiyas.py
"""
import csv
import glob
import math
import os
import statistics as st

import numpy as np

H = os.path.expanduser('~')


def donusler(eylemler):
    yanal = [a for a in eylemler if 1 <= a <= 8]
    ters = sum(abs(((b - c + 4) % 8) - 4) >= 3 for b, c in zip(yanal, yanal[1:]))
    return ters, max(len(yanal) - 1, 1), len(yanal)


def ozet(ad, egim, ters, cift, yanal, n_adim):
    e = np.array(egim)
    print(f'{ad:10s} adim {n_adim:6d} | egim medyan {np.median(e):4.1f}, %95 {np.percentile(e, 95):4.1f}, en cok {e.max():5.1f} derece | '
          f'yanal pay {yanal / n_adim:.2f} | ters donus orani {ters / cift:.3f} (40 adimda ~{40 * ters / n_adim:.1f})')


# AirSim
K = sorted(glob.glob(f'{H}/eland_veri/_gunlukler/airsim_inis_f7_rl_k10_gt_*/'))[-1]
egim, ters, cift, yanal, n = [], 0, 0, 0, 0
for p in sorted(glob.glob(f'{K}k*/politika.csv')):
    rs = [r for r in csv.DictReader(open(p)) if float(r['z_cam']) > 5.0]
    if not rs:
        continue
    ey = [int(r['action']) for r in rs]
    egim += [float(r['tilt_deg']) for r in rs]
    t, c, y = donusler(ey)
    ters, cift, yanal, n = ters + t, cift + c, yanal + y, n + len(ey)
ozet('AirSim', egim, ters, cift, yanal, n)

# light environment
from stable_baselines3 import PPO  # noqa: E402

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv  # noqa: E402
from eland_rl.pilots import shield  # noqa: E402
from eland_rl.scenes import load_list  # noqa: E402

scenes = load_list(f'{H}/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                   **REWARD_PRESETS['zemin_v1']))
model = PPO.load(f'{H}/rl_inis/kos/arama/t3_c23_b1_adim05_alcal1_s1/model.zip', device='cpu')
egim, ters, cift, yanal, n = [], 0, 0, 0, 0
for i in range(len(scenes)):
    for k in range(2):
        obs, _ = env.reset(seed=k, options={'scene_index': i})
        ey = []
        while True:
            pos, R = env.veh.delayed_pose()
            a = shield(int(model.predict(obs, deterministic=True)[0]), obs, pos[2], 10.0)[0]
            egim.append(math.degrees(math.acos(min(1.0, abs(float(R[2, 2]))))))
            ey.append(a)
            obs, _, done, trunc, _ = env.step(a)
            if done or trunc:
                break
        t, c, y = donusler(ey)
        ters, cift, yanal, n = ters + t, cift + c, yanal + y, n + len(ey)
ozet('hafif', egim, ters, cift, yanal, n)
