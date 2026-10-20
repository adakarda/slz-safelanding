"""Screen reward variants before training anything (same 75 episodes, nominal dynamics, 30 s).

For each variant: mean total reward of fixed pilots. A good reward makes the
searching oracle clearly beat straight descent, and keeps aimless pilots
(random lateral wandering, hovering) clearly worse than both.
"""
import math
import sys
from dataclasses import replace

import numpy as np

from eland_rl.camera import Camera, ground_hits, rotation
from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scenes import load_list

VARIANTS = {
    'paper': {},
    'alcal_0.5': dict(a_descend=0.5),
    'alcal_0.3': dict(a_descend=0.3),
    'alcal_0': dict(a_descend=0.0, a_lateral=0.0),
    'alcal_0.3_sure_45': dict(a_descend=0.3, max_t=45.0),
}

scenes = load_list(sys.argv[1])
cam = Camera(128)
safe = np.zeros(8, bool)
safe[[0, 1]] = True
targets = []
for sc in scenes:
    hx, hy = sc.half
    pts = [(x, y) for y in np.arange(-hy + 0.5, hy, 1.0) for x in np.arange(-hx + 0.5, hx, 1.0)
           if safe[np.bincount(cam.semantic_depth(sc, np.array([x, y, 5.0]), rotation((0, 0, 1), 0.0))[0].ravel(),
                               minlength=8).argmax()]]
    targets.append(np.array(pts) if pts else np.zeros((0, 2)))


def oracle(env, si, max_d):
    def act(obs):
        X, Y, _ = ground_hits(np.array([[0.0, 0.0, -1.0]]), env.veh.pos, env.veh.attitude())
        c = np.array([X[0], Y[0]])
        T = targets[si]
        if not len(T):
            return 9
        d = np.hypot(*(T - c).T)
        j = int(np.argmin(d))
        if d[j] <= 0.75 or d[j] > max_d:
            return 9
        rel = (math.degrees(math.atan2(T[j, 1] - c[1], T[j, 0] - c[0])) - math.degrees(env.veh.yaw)) % 360.0
        return 1 + int(round(rel / 45.0)) % 8
    return act


print(f'{"varyant":20} {"duz_inis":>9} {"kahin_8m":>9} {"kahin":>9} {"gezgin":>9} {"bekle":>9} | {"fark":>6}  basari duz/k8/k')
for vname, over in VARIANTS.items():
    cfg = replace(EnvConfig(max_t=30.0, randomise_dynamics=False), **over)
    env = LandingEnv(scenes, cfg)
    rng = np.random.default_rng(7)
    res = {}
    for pname in ('duz_inis', 'kahin_8m', 'kahin', 'gezgin', 'bekle'):
        tot, succ = [], []
        for si in range(len(scenes)):
            for k in range(15):
                obs, _ = env.reset(seed=k, options={'scene_index': si})
                if pname == 'duz_inis':
                    act = lambda o: 9  # noqa: E731
                elif pname == 'kahin_8m':
                    act = oracle(env, si, 8.0)
                elif pname == 'kahin':
                    act = oracle(env, si, 1e9)
                elif pname == 'gezgin':      # wanders: random lateral 3 of 4 steps, else descends
                    act = lambda o: 9 if rng.random() < 0.25 else int(rng.integers(1, 9))  # noqa: E731
                else:                        # hovers
                    act = lambda o: 0  # noqa: E731
                R = 0.0
                while True:
                    obs, r, done, _, info = env.step(act(obs))
                    R += r
                    if done:
                        break
                tot.append(R)
                succ.append(info['success'])
        res[pname] = (np.mean(tot), 100 * np.mean(succ))
    print(f'{vname:20} ' + ' '.join(f'{res[p][0]:9.1f}' for p in ('duz_inis', 'kahin_8m', 'kahin', 'gezgin', 'bekle'))
          + f' | {res["kahin_8m"][0] - res["duz_inis"][0]:+6.1f}  '
          + '/'.join(f'{res[p][1]:.0f}' for p in ('duz_inis', 'kahin_8m', 'kahin')), flush=True)
