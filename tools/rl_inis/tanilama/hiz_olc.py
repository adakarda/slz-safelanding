"""Egitim hiz profili: ortam adimi, politika ileri gecisi ve PPO guncellemesi ayri olculur.

    python hiz_olc.py <sahne_listesi>
"""
import cProfile
import pstats
import sys
import time

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import DummyVecEnv

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.policy import POLICY_KWARGS
from eland_rl.scenes import load_list

scenes = load_list(sys.argv[1], dist_cell_m=0.25)[:10]
mk = lambda: LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['sora_v1']))  # noqa: E731
env = mk()
env.reset(seed=0)
rng = np.random.default_rng(0)


def run(n):
    for _ in range(n):
        _, _, term, trunc, _ = env.step(int(rng.integers(10)))
        if term or trunc:
            env.reset()


run(200)
t = time.perf_counter()
run(2000)
dt = (time.perf_counter() - t) / 2000
print(f'ortam adimi: {dt * 1e3:.2f} ms -> tek cekirdekte {1 / dt:.0f} adim/s')
pr = cProfile.Profile()
pr.enable()
run(1000)
pr.disable()
pstats.Stats(pr).sort_stats('tottime').print_stats(10)


class Saat(BaseCallback):
    def __init__(self):
        super().__init__()
        self.roll, self.train, self.t1 = [], [], None

    def _on_rollout_start(self):
        now = time.perf_counter()
        if self.t1 is not None:
            self.train.append(now - self.t1)
        self.t0 = now

    def _on_rollout_end(self):
        self.t1 = time.perf_counter()
        self.roll.append(self.t1 - self.t0)

    def _on_step(self):
        return True


import torch
o = torch.as_tensor(np.stack([env._last_obs] * 4)[None].repeat(1, 0)[0]).float()
for dev in ('cuda', 'cpu'):
    m = PPO('MlpPolicy', DummyVecEnv([mk]), policy_kwargs=POLICY_KWARGS, device=dev, seed=0, verbose=0)
    x = o.to(dev)
    with torch.no_grad():
        for _ in range(20):
            m.policy(x)
        if dev == 'cuda':
            torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(200):
            m.policy(x)
        if dev == 'cuda':
            torch.cuda.synchronize()
    print(f'{dev}: 4 gozlemlik ileri gecis {(time.perf_counter() - t) / 200 * 1e3:.2f} ms')

for dev, bs in (('cuda', 64), ('cuda', 512), ('cpu', 512)):
    venv = DummyVecEnv([mk for _ in range(4)])
    m = PPO('MlpPolicy', venv, policy_kwargs=POLICY_KWARGS, batch_size=bs, device=dev, seed=0, verbose=0)
    s = Saat()
    m.learn(2 * 8192, callback=s)
    print(f'{dev} batch {bs}: rollout 8192 adim {np.mean(s.roll):.1f} s, guncelleme {np.mean(s.train):.1f} s '
          f'-> {8192 / (np.mean(s.roll) + np.mean(s.train)):.0f} adim/s')
    venv.close()
