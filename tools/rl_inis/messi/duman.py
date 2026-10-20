"""Smoke test on MESSI: one shard's memory, env speed, SORA grids, straight-down baseline on test."""
import resource
import time

import numpy as np

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

t0 = time.time()
sc = load_list('/home/arda/eland_veri/rl/messi_ds4/train.txt', shard=(0, 4), dist_cell_m=0.25)
print(f'shard 0: {len(sc)} sahne, yukleme {time.time() - t0:.1f} s, RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3:.0f} MB')
env = LandingEnv(sc, EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['sora_v1']))
env.reset(seed=0)
rng = np.random.default_rng(0)
n, t0, eps = 0, time.time(), 0
while n < 6000:
    _, _, d, _, _ = env.step(int(rng.integers(10)))
    n += 1
    if d:
        eps += 1
        env.reset()
dt = time.time() - t0
print(f'rastgele: {n / dt:.0f} adim/s, {eps} bolum; RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3:.0f} MB (SORA izgaralari tembel kuruluyor)')
for s in sc:
    s._sora_grid(3.0)
print(f'butun izgaralar kurulunca RSS {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3:.0f} MB')
safe = np.array([s._sora_grid(3.0)[0].mean() for s in sc])
print(f'SORA-guvenli alan payi: medyan %{100 * np.median(safe):.1f}, %10-%90: %{100 * np.percentile(safe, 10):.1f}-%{100 * np.percentile(safe, 90):.1f}')
