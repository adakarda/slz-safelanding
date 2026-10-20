"""Why does sora_v1 time out at test? Same 75 starts, sora_v1 reward:
deterministic vs sampled actions, and 30 s vs 90 s limit."""
import collections
import sys
from dataclasses import replace

import numpy as np
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

scenes = load_list(sys.argv[1])
model = PPO.load(sys.argv[2], device='cpu')
for max_t in (30.0, 90.0):
    env = LandingEnv(scenes, replace(EnvConfig(max_t=max_t, randomise_dynamics=False), **REWARD_PRESETS['sora_v1']))
    for det in (True, False):
        oc, ss, ts, R = collections.Counter(), [], [], []
        for si in range(len(scenes)):
            for k in range(15):
                obs, _ = env.reset(seed=k, options={'scene_index': si})
                ret = 0.0
                while True:
                    a = int(model.predict(obs, deterministic=det)[0])
                    obs, r, done, _, info = env.step(a)
                    ret += r
                    if done:
                        break
                oc[info['outcome']] += 1
                ss.append(info['sora_success'])
                ts.append(info['t'])
                R.append(ret)
        print(f'max_t {max_t:4.0f} s, {"argmax " if det else "ornekle"}: SORA basari %{100 * np.mean(ss):5.1f}, odul {np.mean(R):6.1f}, '
              f'sure medyan {np.median(ts):4.1f} s, {dict(oc)}', flush=True)
