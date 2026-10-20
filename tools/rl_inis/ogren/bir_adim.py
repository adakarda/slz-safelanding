"""Learning aid: fly one episode and print, step by step, what the policy saw, the probability it gave
each of the 10 actions, the command it chose, and the reward broken into its parts.

    bash ~/rl_inis/py.sh ogren/bir_adim.py [model.zip] [scene list] [scene index] [start seed]
"""
import sys

import numpy as np
import torch
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

model_path = sys.argv[1] if len(sys.argv) > 1 else '/home/arda/rl_inis/kos/sora_v2_s0/model.zip'
scene_list = sys.argv[2] if len(sys.argv) > 2 else '/home/arda/rl_inis/sahneler_pilot.txt'
si = int(sys.argv[3]) if len(sys.argv) > 3 else 4
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
NAMES = ['dur', 'ileri', 'sol-ileri', 'sol', 'sol-geri', 'geri', 'sag-geri', 'sag', 'sag-ileri', 'alcal']

model = PPO.load(model_path, device='cpu')
obs_mode = 'sem_depth_sora' if model.observation_space.shape[0] == 3 else 'sem_depth'
env = LandingEnv(load_list(scene_list, dist_cell_m=0.25 if 'messi' in scene_list else 0.1),
                 EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode=obs_mode, **REWARD_PRESETS['sora_v1']))
obs, info = env.reset(seed=seed, options={'scene_index': si})
print(f"sahne {info['scene']}, baslangic x {info['start'][0]:.1f} y {info['start'][1]:.1f} irtifa {info['start'][2]:.1f} m, girdi {obs_mode}")
print(' adim  irtifa  guvenli%  SORA%  | en olasi 3 eylem                       | secilen     | zaman  eylem  yaklasma  bitis | toplam')
total = 0.0
while True:
    with torch.no_grad():
        p = model.policy.get_distribution(torch.as_tensor(obs[None])).distribution.probs[0].numpy()
        v = float(model.policy.predict_values(torch.as_tensor(obs[None]))[0])
    a = int(np.argmax(p))
    top = ', '.join(f'{NAMES[i]} %{100 * p[i]:.0f}' for i in np.argsort(p)[::-1][:3])
    h = env.veh.pos[2]
    safe = 100 * np.isin(np.round(obs[0] * 7), [0, 1]).mean()
    sora = 100 * obs[2].mean() if obs.shape[0] == 3 else float('nan')
    obs, r, done, _, inf = env.step(a)
    cfg = env.cfg
    rt = 0.0 if done else cfg.r_step
    end = r - (cfg.w_t * rt + cfg.w_s * inf['r_s'] + cfg.w_c * inf['r_c'] + cfg.w_a * inf['r_a'] + inf['r_shape'])
    total += r
    print(f'{env.steps:5d} {h:6.1f}m {safe:8.1f} {sora:6.1f}  | {top:38s} | {a} {NAMES[a]:9s} | '
          f'{rt:+5.2f} {inf["r_a"]:+6.2f} {inf["r_shape"]:+8.2f} {end:+6.1f} | {total:+7.1f}   (critic beklentisi {v:+6.1f})')
    if done:
        break
print(f"sonuc: {inf['outcome']}, SORA-guvenli: {inf['sora_success']}, sure {inf['t']:.1f} s, toplam odul {total:+.1f}")
