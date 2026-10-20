"""RL + SORA shield: the policy flies; below shield_h, a 'descend' over a centre the SORA channel
calls unsafe is replaced by a slide towards the nearest SORA-safe pixel (or a hold if none).
Same 75 starts, sora_v1, 30 s, nominal dynamics. No training."""
import collections
import math
import sys

import numpy as np
from stable_baselines3 import PPO

from eland_rl.camera import sora_channel
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

scenes = load_list(sys.argv[1])
env = LandingEnv(scenes, EnvConfig(max_t=float(__import__('os').environ.get('MAXT', '30')), randomise_dynamics=False, obs_mode='sem_depth_sora',
                                   **REWARD_PRESETS['sora_v1']))


def slide_to_safe(ch):
    ys, xs = np.nonzero(ch)
    if not len(ys):
        return 0
    dx, dy = xs - 64 + 0.5, (ys - 64 + 0.5) * 0.75
    j = int(np.argmin(dx * dx + dy * dy))
    return 1 + int(round((math.degrees(math.atan2(-dx[j], -dy[j])) % 360.0) / 45.0)) % 8


for path in sys.argv[2:]:
    model = PPO.load(path, device='cpu')
    for shield_h in (None, 10.0):
        oc, ss, ts, R, overrides = collections.Counter(), [], [], [], 0
        for si in range(len(scenes)):
            for k in range(15):
                obs, _ = env.reset(seed=k, options={'scene_index': si})
                ret = 0.0
                while True:
                    a = int(model.predict(obs, deterministic=True)[0])
                    h = env.veh.delayed_pose()[0][2]
                    if shield_h is not None and a == 9 and h < shield_h and not obs[2, 62:66, 62:66].all():
                        a = slide_to_safe(obs[2] > 0.5)
                        overrides += 1
                    obs, r, done, _, info = env.step(a)
                    ret += r
                    if done:
                        break
                oc[info['outcome']] += 1
                ss.append(info['sora_success'])
                ts.append(info['t'])
                R.append(ret)
        tag = 'kalkansiz' if shield_h is None else f'kalkan < {shield_h:.0f} m'
        print(f'{path.split("/")[-2]:12s} {tag:14s} SORA basari %{100 * np.mean(ss):5.1f}, odul {np.mean(R):6.1f}, '
              f'sure medyan {np.median(ts):4.1f} s, kalkan devrede {overrides} adim, {dict(oc)}', flush=True)
