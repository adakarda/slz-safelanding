"""Is the reward wrong, or did the agent fail to find the behaviour it rewards?

Same 75 evaluation episodes (5 scenes x 15 starts, nominal dynamics, 30 s).
Total reward of:
  duz_inis   always descend
  kahin      knows the ground truth: slides to the nearest point where a 5 m
             view has a safe majority (the paper's success rule), then descends
  rl         the pilot policy
If kahin earns more than duz_inis, the reward prefers the right behaviour and
the failure is the agent's (exploration/optimisation). If not, the reward
itself prefers straight descent.
"""
import math
import sys

import numpy as np

from eland_rl.camera import Camera, ground_hits, rotation
from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scenes import load_list

GRID = 1.0
scenes = load_list(sys.argv[1])
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False))
cam = Camera(128)
safe = np.zeros(8, bool)
safe[[0, 1]] = True
targets = []
for sc in scenes:
    hx, hy = sc.half
    pts = []
    for y in np.arange(-hy + GRID / 2, hy, GRID):
        for x in np.arange(-hx + GRID / 2, hx, GRID):
            sem, _ = cam.semantic_depth(sc, np.array([x, y, 5.0]), rotation((0, 0, 1), 0.0))
            if safe[np.bincount(sem.ravel(), minlength=8).argmax()]:
                pts.append((x, y))
    targets.append(np.array(pts) if pts else np.zeros((0, 2)))


def kahin(si, max_d=1e9):
    def act(obs):
        pos, R = env.veh.pos, env.veh.attitude()
        X, Y, _ = ground_hits(np.array([[0.0, 0.0, -1.0]]), pos, R)
        c = np.array([X[0], Y[0]])
        T = targets[si]
        if not len(T):
            return 9
        d = np.hypot(*(T - c).T)
        j = int(np.argmin(d))
        if d[j] <= 0.75 or d[j] > max_d:
            return 9
        world = math.degrees(math.atan2(T[j, 1] - c[1], T[j, 0] - c[0]))
        rel = (world - math.degrees(env.veh.yaw)) % 360.0
        return 1 + int(round(rel / 45.0)) % 8
    return act


model = None
if len(sys.argv) > 2:
    from stable_baselines3 import PPO
    model = PPO.load(sys.argv[2], device='cpu')
results = {}
from collections import Counter
for name in ('duz_inis', 'kahin', 'kahin_2m', 'kahin_4m', 'kahin_8m', 'rl'):
    if name == 'rl' and model is None:
        continue
    oc = Counter()
    tot, succ, lens = [], [], []
    for si in range(len(scenes)):
        for k in range(15):
            obs, _ = env.reset(seed=k, options={'scene_index': si})
            if name == 'duz_inis':
                act = lambda o: 9  # noqa: E731
            elif name.startswith('kahin'):
                act = kahin(si, float(name.split('_')[1][:-1]) if '_' in name else 1e9)
            else:
                act = lambda o: int(model.predict(o, deterministic=True)[0])  # noqa: E731
            R, n = 0.0, 0
            while True:
                obs, r, done, _, info = env.step(act(obs))
                R += r
                n += 1
                if done:
                    break
            oc[info['outcome']] += 1
            tot.append(R)
            succ.append(info['success'])
            lens.append(n)
    tot = np.array(tot)
    results[name] = tot
    print(f'{name:9s} toplam odul ort {tot.mean():6.1f} (medyan {np.median(tot):6.1f}), basari %{100 * np.mean(succ):.1f}, '
          f'adim ort {np.mean(lens):.0f}  {dict(oc)}')
if 'kahin' in results:
    d = results['kahin'] - results['duz_inis']
    print(f'kahin - duz_inis: ort {d.mean():+.1f}; kahinin daha cok puan aldigi bolum {int((d > 0).sum())}/{len(d)}')
