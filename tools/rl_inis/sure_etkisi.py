"""Teshis (tanimlayici, karar yok): ayni model, ayni 320 deneme, test suresi 30 / 60 / 90 s. Basarisizlik turleri.

    bash ~/rl_inis/py.sh sure_etkisi.py MODEL.zip
"""
import collections
import sys

from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.pilots import shield
from eland_rl.scenes import load_list

model = PPO.load(sys.argv[1], device='cpu')
scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
for max_t in (30.0, 60.0, 90.0):
    env = LandingEnv(scenes, EnvConfig(max_t=max_t, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                       **REWARD_PRESETS['zemin_v1']))
    for kalkan in (False, True):
        sonuc = collections.Counter()
        for i in range(len(scenes)):
            for k in range(10):
                obs, _ = env.reset(seed=k, options={'scene_index': i})
                while True:
                    a = int(model.predict(obs, deterministic=True)[0])
                    if kalkan:
                        a = shield(a, obs, env.veh.delayed_pose()[0][2], 10.0)[0]
                    obs, r, done, trunc, info = env.step(a)
                    if done or trunc:
                        break
                key = 'basari' if info['zemin_success'] else info['outcome']
                sonuc[key] += 1
                if info['zemin_success'] and info['soft_landing']:
                    sonuc['(cim)'] += 1
        n = sum(v for k, v in sonuc.items() if k != '(cim)')
        print(f'{max_t:4.0f} s {"kalkan" if kalkan else "      "}: ' +
              '  '.join(f'{k} {100 * v / n:5.1f}%' for k, v in sorted(sonuc.items())), flush=True)
