"""Pilot diagnosis: is a successful landing reachable at all from the evaluation starts?

For every scene: on a 0.5 m grid, would a level camera at 5 m above (x, y) see a
safe majority class (the paper's success rule)? Then, for each of the 15
starts, the distance to the nearest such point and the ideal time to fly there
(descend 2 m/s and move 1 m/s cannot happen in the same step, so the times
add up). Also the same with the SORA rule (centre landable and >= 3 m from a
hazard). Upper bounds for the light environment, not a policy.
"""
import sys

import numpy as np

from eland_rl.camera import Camera, rotation
from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scenes import load_list

scenes = load_list(sys.argv[1])
env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False))
cam = Camera(128)
safe = np.zeros(8, bool)
safe[[0, 1]] = True
for si, sc in enumerate(scenes):
    hx, hy = sc.half
    xs = np.arange(-hx + 0.25, hx, 0.5)
    ys = np.arange(-hy + 0.25, hy, 0.5)
    ok = np.zeros((len(ys), len(xs)), bool)
    sora = np.zeros_like(ok)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            sem, _ = cam.semantic_depth(sc, np.array([x, y, 5.0]), rotation((0, 0, 1), 0.0))
            ok[j, i] = safe[np.bincount(sem.ravel(), minlength=8).argmax()]
            c = sc.classes_at(np.array([x]), np.array([y]))[0]
            sora[j, i] = safe[c] and sc.hazard_distance(x, y) >= 3.0
    gx, gy = np.meshgrid(xs, ys)
    sat = []
    for k in range(15):
        _, info = env.reset(seed=k, options={'scene_index': si})
        x0, y0, h, _ = info['start']
        d = np.hypot(gx - x0, gy - y0)
        d_ok = d[ok].min() if ok.any() else np.inf
        d_so = d[ok & sora].min() if (ok & sora).any() else np.inf
        t_ideal = (h - 5.0) / 2.0 + d_ok / 1.0
        sat.append((d_ok, d_so, t_ideal))
    s = np.array(sat)
    print(f'{sc.name}: basari alani %{100 * ok.mean():.1f}, basari+SORA alani %{100 * (ok & sora).mean():.1f}; '
          f'15 baslangicta en yakin basari noktasi medyan {np.median(s[:, 0]):.1f} m (en cok {s[:, 0].max():.1f}), '
          f'SORA ile medyan {np.median(s[:, 1]):.1f} m; ideal sure medyan {np.median(s[:, 2]):.1f} s; '
          f'altinda basari olan baslangic {int((s[:, 0] < 0.5).sum())}/15')
