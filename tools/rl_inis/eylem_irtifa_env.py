"""Bir modelin hafif ortamda irtifa bandina gore eylem dagilimi (AirSim'deki 'hep alcaliyor' gozlemiyle kiyas icin).

    bash ~/rl_inis/py.sh eylem_irtifa_env.py MODEL.zip [ODUL] [BASLANGIC_SAYISI]
"""
import collections
import sys

from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

model = PPO.load(sys.argv[1], device='cpu')
odul = sys.argv[2] if len(sys.argv) > 2 else 'zemin_v1'
n = int(sys.argv[3]) if len(sys.argv) > 3 else 3
scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', **REWARD_PRESETS[odul]))
bant = collections.defaultdict(collections.Counter)
ilk_yanal = []
sonuc = collections.Counter()
for i in range(len(scenes)):
    for k in range(n):
        obs, info = env.reset(seed=k, options={'scene_index': i})
        ilk = None
        while True:
            h = float(env.veh.delayed_pose()[0][2])
            a = int(model.predict(obs, deterministic=True)[0])
            bant[int(h // 5) * 5][a] += 1
            if a != 9 and ilk is None:
                ilk = h
            obs, r, done, trunc, info = env.step(a)
            if done or trunc:
                break
        ilk_yanal.append(ilk)
        sonuc[(info['outcome'], int(info['zemin_success']))] += 1
for b in sorted(bant, reverse=True):
    c = bant[b]
    t = sum(c.values())
    print(f'{b:3d}-{b + 5:3d} m: {t:5d} adim  alcal {100 * c[9] / t:5.1f}%  dur {100 * c[0] / t:4.1f}%  yanal {100 * (t - c[9] - c[0]) / t:5.1f}%')
yan = [x for x in ilk_yanal if x is not None]
print(f'bolum {len(ilk_yanal)}; hic yanal yok {len(ilk_yanal) - len(yan)}; ilk yanal eylem irtifasi medyan '
      f'{sorted(yan)[len(yan) // 2]:.1f} m' if yan else 'yanal yok')
print(dict(sonuc))
