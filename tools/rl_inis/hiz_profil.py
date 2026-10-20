"""Ortam hizi: D ayari (30 s) ile C ayari (90 s), rastgele eylemler, ayni sahneler; adim/s ve reset payi."""
import cProfile
import pstats
import sys
import time

import numpy as np

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

scenes = load_list('/home/arda/eland_veri/rl/messi_ds4/train_b.txt', dist_cell_m=0.25)[:40]
for ad, kw in (('C (90 s)', {}), ('D (30 s)', {'max_t': 30.0})):
    env = LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', sora_metric=False, **kw, **REWARD_PRESETS['zemin_v1']))
    rng = np.random.default_rng(0)
    env.reset(seed=0)
    n, t_reset, nres = 0, 0.0, 0
    t0 = time.perf_counter()
    while n < 4000:
        _, _, done, trunc, _ = env.step(int(rng.choice([9, 9, 9, 1, 3, 5, 7])))
        n += 1
        if done or trunc:
            a = time.perf_counter()
            env.reset()
            t_reset += time.perf_counter() - a
            nres += 1
    dt = time.perf_counter() - t0
    print(f'{ad}: {n / dt:6.0f} adim/s (ortam yalniz), bolum {nres}, reset {1000 * t_reset / max(nres, 1):.1f} ms/bolum, '
          f'reset payi {100 * t_reset / dt:.0f} %')
if len(sys.argv) > 1:
    env = LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', sora_metric=False, max_t=30.0, **REWARD_PRESETS['zemin_v1']))
    env.reset(seed=0)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(2000):
        _, _, d, t, _ = env.step(9)
        if d or t:
            env.reset()
    pr.disable()
    pstats.Stats(pr).sort_stats('cumulative').print_stats(14)
