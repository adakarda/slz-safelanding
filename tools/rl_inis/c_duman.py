"""zemin_v2 duman testi: gercek val sahnelerinde ortam kurulur, rastgele bolumler kosar, yumusak cekim olculur."""
import collections
import time

import numpy as np

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/val_b32.txt', dist_cell_m=0.25)[:6]
t0 = time.time()
env = LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', sora_metric=False, **REWARD_PRESETS['zemin_v2']))
rng = np.random.default_rng(0)
son = collections.Counter()
fark = []
for k in range(12):
    obs, info = env.reset(seed=k)
    p = env.veh.pos
    d_any = env.scene.nearest_target(p[0], p[1], (6, 5), 2.0)[2]
    d_soft = env.scene.nearest_target(p[0], p[1], (6, 5), 2.0, (0,))[2]
    fark.append((round(d_any, 1), round(d_soft, 1), round(env._phi, 1)))
    while True:
        obs, r, done, trunc, info = env.step(int(rng.integers(10)))
        if done or trunc:
            son[(info['outcome'], info['landing_class'], info['r_end'])] += 1
            break
print(f'{time.time() - t0:.1f} s; (d_any, d_soft, phi) {fark}')
print(dict(son))
