"""Screen our SORA reward variants before training (same 75 episodes, nominal dynamics, 30 s).

Success everywhere is SORA's: the point under the vehicle at 5 m is a landable
class and >= 3 m from structure / water / vehicle / person. Pilots:
  duz_inis    always descend
  sk_D        SORA oracle: slides to the nearest SORA-safe point if it is within D m, then descends
  gezgin      wanders (random lateral 3 of 4 steps)
  bekle       hovers
A good reward: the best oracle clearly above straight descent, wanderers and
hovering clearly below both.
"""
import math
import sys
from dataclasses import replace

import numpy as np

from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scenes import load_list

S = dict(success_rule='sora')
VARIANTS = {
    'paper (cogunluk)': {},
    'S0 sora bitis': dict(S),
    'S1 +sekil k=1': dict(S, shaping_k=1.0),
    'S2 +sekil k=2': dict(S, shaping_k=2.0),
    'S3 k=1 alcal 0.5': dict(S, shaping_k=1.0, a_descend=0.5),
    'S4 k=2 alcal 0.5': dict(S, shaping_k=2.0, a_descend=0.5),
    'S5 k=2 alcal 0.5 gorus 0': dict(S, shaping_k=2.0, a_descend=0.5, w_s=0.0),
    'S6 = S5, disari -50': dict(S, shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0),
}
if len(sys.argv) > 2:
    VARIANTS = {k: v for k, v in VARIANTS.items() if k[:2] in sys.argv[2].split(',')}
PILOTS = ('duz_inis', 'sk_4', 'sk_8', 'sk_15', 'sk_99', 'gezgin', 'bekle', 'kacak')
scenes = load_list(sys.argv[1])


def sora_oracle(env, max_d):
    def act(obs):
        x, y = env.veh.pos[0], env.veh.pos[1]
        tx, ty, d = env.scene.nearest_sora_safe(x, y)
        if d <= 0.5 or d > max_d:
            return 9
        rel = (math.degrees(math.atan2(ty - y, tx - x)) - math.degrees(env.veh.yaw)) % 360.0
        return 1 + int(round(rel / 45.0)) % 8
    return act


print(f'{"varyant":26}' + ''.join(f'{p:>9}' for p in PILOTS) + ' | en iyi kahin - duz | SORA basari % duz/sk8/sk15/sk99')
for vname, over in VARIANTS.items():
    env = LandingEnv(scenes, replace(EnvConfig(max_t=30.0, randomise_dynamics=False), **over))
    rng = np.random.default_rng(7)
    res = {}
    for p in PILOTS:
        tot, ss = [], []
        for si in range(len(scenes)):
            for k in range(15):
                obs, _ = env.reset(seed=k, options={'scene_index': si})
                if p == 'duz_inis':
                    act = lambda o: 9  # noqa: E731
                elif p.startswith('sk_'):
                    act = sora_oracle(env, float(p[3:]))
                elif p == 'kacak':           # flies straight out of the scene
                    act = lambda o: 1  # noqa: E731
                elif p == 'gezgin':
                    act = lambda o: 9 if rng.random() < 0.25 else int(rng.integers(1, 9))  # noqa: E731
                else:
                    act = lambda o: 0  # noqa: E731
                R = 0.0
                while True:
                    obs, r, done, _, info = env.step(act(obs))
                    R += r
                    if done:
                        break
                tot.append(R)
                ss.append(info['sora_success'])
        res[p] = (np.mean(tot), 100 * np.mean(ss))
    best = max(res[p][0] for p in PILOTS if p.startswith('sk_'))
    print(f'{vname:26}' + ''.join(f'{res[p][0]:9.1f}' for p in PILOTS)
          + f' | {best - res["duz_inis"][0]:+8.1f}           | '
          + '/'.join(f'{res[p][1]:.0f}' for p in ('duz_inis', 'sk_8', 'sk_15', 'sk_99')), flush=True)
