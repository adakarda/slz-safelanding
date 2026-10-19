"""Bir modelin hafif ortamdaki eylem turleri: alcal, dur, duz kayma (1-8), kayarken alcal (10-17); sonuc ve sure.

    bash ~/rl_inis/py.sh eylem_turu.py MODEL.zip [--diag]
"""
import collections
import statistics as st
import sys

from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

model = PPO.load(sys.argv[1], device='cpu')
diag = '--diag' in sys.argv
scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', diag_actions=diag,
                                   **REWARD_PRESETS['zemin_v1']))
tur = collections.Counter()
son = collections.Counter()
sure = []
for i in range(len(scenes)):
    for k in range(3):
        obs, _ = env.reset(seed=k, options={'scene_index': i})
        while True:
            a = int(model.predict(obs, deterministic=True)[0])
            tur['alcal' if a == 9 else 'dur' if a == 0 else 'kayarken alcal' if a >= 10 else 'duz kayma'] += 1
            obs, r, done, trunc, info = env.step(a)
            if done or trunc:
                break
        son['basari' if info['zemin_success'] else info['outcome']] += 1
        if info['zemin_success']:
            sure.append(info['t'])
n = sum(tur.values())
print('eylemler: ' + ', '.join(f'{k} {100 * v / n:.1f} %' for k, v in tur.most_common()))
print(f'sonuc {dict(son)}; basarili sure {st.mean(sure):.1f} s' if sure else f'sonuc {dict(son)}')
