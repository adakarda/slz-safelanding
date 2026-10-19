"""Teshis (tanimlayici): ayni model, val_b32'nin 320 denemesi; argmax ile ve olasilikla eylem secimi.
Ayrica argmax'ta eylem olasiliklarinin toplami: alcalan eylemler (9, 10..17) ile yatay eylemler.

    bash ~/rl_inis/py.sh stokastik_test.py MODEL.zip [--diag]
"""
import statistics as st
import sys

import numpy as np
import torch
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.pilots import shield
from eland_rl.scenes import load_list

model = PPO.load(sys.argv[1], device='cpu')
diag = '--diag' in sys.argv
scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', diag_actions=diag,
                                   **REWARD_PRESETS['zemin_v1']))
torch.manual_seed(0)
alcalan_pay = []
for deterministik in (True, False):
    for kalkan in (False, True):
        ok, sure, n = 0, [], 0
        for i in range(len(scenes)):
            for k in range(10):
                obs, _ = env.reset(seed=k, options={'scene_index': i})
                while True:
                    if deterministik and not kalkan and n < 3000:
                        with torch.no_grad():
                            p = model.policy.get_distribution(model.policy.obs_to_tensor(obs)[0]).distribution.probs[0].numpy()
                        alcalan_pay.append(p[9] + (p[10:].sum() if len(p) > 10 else 0.0))
                        n += 1
                    a = int(model.predict(obs, deterministic=deterministik)[0])
                    if kalkan:
                        a = shield(a, obs, env.veh.delayed_pose()[0][2], 10.0)[0]
                    obs, r, done, trunc, info = env.step(a)
                    if done or trunc:
                        break
                if info['zemin_success']:
                    ok += 1
                    sure.append(info['t'])
        print(f'{"argmax    " if deterministik else "olasilikla"} {"kalkanli " if kalkan else "kalkansiz"}: basari {100 * ok / 320:5.1f} %, '
              f'basarili sure {st.mean(sure) if sure else float("nan"):5.1f} s', flush=True)
print(f'argmax adimlarinda alcalan eylemlerin toplam olasiligi: medyan {np.median(alcalan_pay):.2f}')
