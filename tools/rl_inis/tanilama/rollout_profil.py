"""Rollout dongusunun hafif profili: CPU, n_steps 128, 3 sahne. Nerede vakit gidiyor?"""
import cProfile
import os
import pstats
import sys
import time

import torch
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.policy import POLICY_KWARGS
from eland_rl.scenes import load_list

if len(sys.argv) > 2:
    torch.set_num_threads(int(sys.argv[2]))
scenes = load_list(sys.argv[1], dist_cell_m=0.25)
mk = lambda: Monitor(LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['sora_v1'])))  # noqa: E731
m = PPO('MlpPolicy', DummyVecEnv([mk for _ in range(4)]), n_steps=128, batch_size=64, n_epochs=1,
        policy_kwargs=POLICY_KWARGS, device='cpu', seed=0, verbose=0)
m.learn(512)
pr = cProfile.Profile()
t = time.perf_counter()
pr.enable()
m.learn(4 * 512, reset_num_timesteps=False)
pr.disable()
print(f'torch threads {torch.get_num_threads()}, OMP {os.environ.get("OMP_NUM_THREADS")}: '
      f'{(time.perf_counter() - t):.1f} s / 2048 adim')
pstats.Stats(pr).sort_stats('cumulative').print_stats(28)
