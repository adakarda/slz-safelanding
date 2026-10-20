"""A1 politikasini evaluate.py ile ayni baslangiclarda kos; inis noktasini 0/1/2/3 m tamponla yargila.
Politika ve gozlem degismez (3 m'lik SORA kanali); sadece basari olcutu degisir."""
import sys

import numpy as np
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.evaluate import run
from eland_rl.pilots import shield
from eland_rl.scenes import load_list

scenes = load_list(sys.argv[1], dist_cell_m=0.25)
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', **REWARD_PRESETS['sora_v1']))
model = PPO.load(sys.argv[2], device='cpu')
rl = lambda o: int(model.predict(o, deterministic=True)[0])  # noqa: E731
methods = {'rl': rl, 'rl_kalkan': lambda o: shield(rl(o), o, env.veh.delayed_pose()[0][2], 10.0)[0], 'duz_inis': lambda o: 9}
for name, act in methods.items():
    ok = {m: 0 for m in (0.0, 1.0, 2.0, 3.0)}
    n, out = 0, {}
    for i, sc in enumerate(scenes):
        for k in range(15):
            info, _, _ = run(env, act, i, k)
            n += 1
            out[info['outcome']] = out.get(info['outcome'], 0) + 1
            if info['outcome'] in ('safe_landing', 'unsafe_landing'):
                x, y = info['landing_xy']
                for m in ok:
                    ok[m] += sc.is_sora_safe(x, y, m)
    print(f'{name:10s} n={n} ' + '  '.join(f'tampon {m:.0f} m: %{ok[m] / n * 100:5.1f}' for m in ok) + f'   {out}', flush=True)
