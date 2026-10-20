"""F4 pilot: Gazebo + PX4 runs against the light environment, start by start.

For each start k: the env episode with the same start (nominal dynamics, the
same model), and the Gazebo run's policy log after the mode was activated.
Outcome rule as in the env (rl_f0_onkayit.md, amendment 3): the first logged
tick at or below 5 m, its full-view majority class, within 30 s of activation.

    python analiz.py <run_dir_prefix e.g. kos/gt_b> <model.zip> <scenes.txt>
"""
import csv
import glob
import math
import os
import sys

import numpy as np

from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scene import Scene
from eland_rl.scenes import load_list

prefix, model_path, scene_list = sys.argv[1:4]
from stable_baselines3 import PPO  # noqa: E402

model = PPO.load(model_path, device='cpu')
env = LandingEnv(load_list(scene_list), EnvConfig(max_t=30.0, randomise_dynamics=False))
gz_scene = Scene.from_messi('/home/arda/v3_test/foto/fotoo/DJI_0097.JPG', '/home/arda/v3_test/maske/fotomask/DJI_0097.png',
                            size_m=(64.02, 42.68))
SAFE = {0, 1}


def env_run(k):
    obs, info = env.reset(seed=k, options={'scene_index': 0})
    x0, y0 = info['start'][0], info['start'][1]
    acts = []
    while True:
        a = int(model.predict(obs, deterministic=True)[0])
        acts.append(a)
        obs, _, done, _, info = env.step(a)
        if done:
            lx, ly = info['landing_xy']
            return dict(outcome=info['outcome'], success=info['success'], sora_ok=info['sora_ok'], t=info['t'],
                        lateral=sum(1 <= x <= 8 for x in acts), n=len(acts), x=lx, y=ly,
                        move=math.hypot(lx - x0, ly - y0))


rows = []
for d in sorted(glob.glob(f'{prefix}*'), key=lambda p: int(p.rsplit('b', 1)[1])):
    k = int(d.rsplit('b', 1)[1])
    e = env_run(k)
    g = dict(outcome='kayit_yok')
    pc, ml = os.path.join(d, 'politika.csv'), os.path.join(d, 'mod.log')
    t_on = None
    if os.path.exists(ml):
        for line in open(ml):
            if 'RL Landing active' in line:
                t_on = float(line.split('[')[2].split(']')[0])     # ROS log stamp = wall clock
                break
    if os.path.exists(pc) and t_on is not None:
        L = [r for r in csv.DictReader(open(pc)) if float(r['t_wall']) >= t_on]
        if L:
            t0 = float(L[0]['t_sim'])
            x0, y0 = float(L[0]['x']), float(L[0]['y'])
            low = next((r for r in L if float(r['z_cam']) <= 5.0), None)
            before = L if low is None else L[:L.index(low) + 1]
            lat = sum(1 <= int(r['action']) <= 8 for r in before)
            last = L[-1]
            lx, ly = float(last['x']), float(last['y'])
            if low is None:
                g = dict(outcome='5m_yok', lateral=lat, n=len(before))
            else:
                t = float(low['t_sim']) - t0
                ok = int(low['majority']) in SAFE
                out = 'timeout' if t > 30.0 else ('safe_landing' if ok else 'unsafe_landing')
                sora = gz_scene.hazard_distance(lx, ly)
                cls = int(gz_scene.classes_at(np.array([lx]), np.array([ly]))[0])
                g = dict(outcome=out, success=out == 'safe_landing', sora_ok=out == 'safe_landing' and sora >= 3.0 and cls in SAFE,
                         t=t, lateral=lat, n=len(before), x=lx, y=ly, move=math.hypot(lx - x0, ly - y0),
                         tilt_max=max(float(r['tilt_deg']) for r in before),
                         infer_ms=float(np.median([float(r['infer_ms']) for r in L])))
    rows.append((k, e, g))

print(f'{"b":>3} | {"ortam sonuc":15} {"t":>5} {"yanal":>5} {"kayma":>6} | {"gazebo sonuc":15} {"t":>5} {"yanal":>5} '
      f'{"kayma":>6} {"egim":>5} | {"inis farki":>9}')
for k, e, g in rows:
    dx = math.hypot(e['x'] - g['x'], e['y'] - g['y']) if 'x' in g else float('nan')
    print(f'{k:>3} | {e["outcome"]:15} {e["t"]:5.1f} {e["lateral"]:5d} {e["move"]:6.2f} | {g["outcome"]:15} '
          f'{g.get("t", float("nan")):5.1f} {g.get("lateral", 0):5d} {g.get("move", float("nan")):6.2f} '
          f'{g.get("tilt_max", float("nan")):5.1f} | {dx:9.2f}')
n = len(rows)
es = sum(e['success'] for _, e, _ in rows)
gs = sum(bool(g.get('success')) for _, _, g in rows)
same = sum(e['outcome'] == g['outcome'] for _, e, g in rows)
print(f'\nbasari: ortam {es}/{n}, gazebo {gs}/{n}; ayni sonuc {same}/{n}; '
      f'SORA uyumlu: ortam {sum(e["sora_ok"] for _, e, _ in rows)}/{n}, gazebo {sum(bool(g.get("sora_ok")) for _, _, g in rows)}/{n}')
d = [math.hypot(e['x'] - g['x'], e['y'] - g['y']) for _, e, g in rows if 'x' in g]
if d:
    print(f'inis noktasi farki (ortam - gazebo): medyan {np.median(d):.2f} m, en cok {max(d):.2f} m')
    print(f'gazebo politika cikarim suresi medyan {np.median([g["infer_ms"] for _, _, g in rows if "infer_ms" in g]):.1f} ms')
