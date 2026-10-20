"""Can SORA-safe ground be found from what the camera sees? Oracle limited to the current view.

gorus_kahini: knows SORA safety only for ground points inside the current
128x128 camera footprint; slides to the nearest such point (from the vehicle),
descends when above one, descends straight if none is visible. Compared with
the global oracle (whole map) and straight descent; same 75 starts, sora_v1, 30 s.
"""
import math
import sys
from dataclasses import replace

import numpy as np

from eland_rl.camera import ground_hits
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

scenes = load_list(sys.argv[1])
env = LandingEnv(scenes, replace(EnvConfig(max_t=30.0, randomise_dynamics=False), **REWARD_PRESETS['sora_v1']))


def toward(tx, ty):
    x, y = env.veh.pos[0], env.veh.pos[1]
    rel = (math.degrees(math.atan2(ty - y, tx - x)) - math.degrees(env.veh.yaw)) % 360.0
    return 1 + int(round(rel / 45.0)) % 8


def view_oracle(obs):
    x, y = env.veh.pos[0], env.veh.pos[1]
    if env.scene.is_sora_safe(x, y):
        return 9
    pos, R = env.veh.delayed_pose()
    X, Y, t = ground_hits(env.cam.rays, pos, R)
    ok = np.isfinite(t) & env.scene.inside(X, Y)
    safe, _, _ = env.scene._sora_grid(3.0)
    gh, gw = safe.shape
    v = np.clip(((0.5 - Y / env.scene.size[1]) * gh).astype(int), 0, gh - 1)
    u = np.clip(((X / env.scene.size[0] + 0.5) * gw).astype(int), 0, gw - 1)
    m = ok & safe[v, u]
    if not m.any():
        return 9
    d = np.hypot(X[m] - x, Y[m] - y)
    j = int(np.argmin(d))
    return 9 if d[j] <= 0.5 else toward(X[m][j], Y[m][j])


def global_oracle(obs):
    x, y = env.veh.pos[0], env.veh.pos[1]
    tx, ty, d = env.scene.nearest_sora_safe(x, y)
    return 9 if d <= 0.5 else toward(tx, ty)


for name, act in (('duz_inis', lambda o: 9), ('gorus_kahini', view_oracle), ('tum_harita_kahini', global_oracle)):
    ss, R, visible = [], [], []
    for si in range(len(scenes)):
        for k in range(15):
            obs, _ = env.reset(seed=k, options={'scene_index': si})
            ret = 0.0
            while True:
                obs, r, done, _, info = env.step(act(obs))
                ret += r
                if done:
                    break
            ss.append(info['sora_success'])
            R.append(ret)
    print(f'{name:18s} SORA basari %{100 * np.mean(ss):5.1f}, odul {np.mean(R):6.1f}', flush=True)


from eland_rl.camera import sora_channel  # noqa: E402


def channel_pilot(obs):
    """Uses only what the vehicle can compute: the 128x128 classes it sees and its height.
    Descends when the image centre is SORA-safe in the channel, else slides towards the nearest
    SORA-safe pixel (image up = nose), else descends."""
    sem = np.round(obs[0] * 7).astype(np.uint8)
    h = env.veh.delayed_pose()[0][2]
    ch = sora_channel(sem, h)
    c = 64
    if ch[c - 2:c + 2, c - 2:c + 2].all():
        return 9
    ys, xs = np.nonzero(ch)
    if not len(ys):
        return 9
    # 128x128 is stretched from 4:3: a row step is 0.75 of a column step on the ground
    dx, dy = xs - c + 0.5, (ys - c + 0.5) * 0.75
    j = int(np.argmin(dx * dx + dy * dy))
    ang = math.degrees(math.atan2(-dx[j], -dy[j])) % 360.0     # 0 = image up = nose, counter-clockwise
    return 1 + int(round(ang / 45.0)) % 8


ss, R = [], []
for si in range(len(scenes)):
    for k in range(15):
        obs, _ = env.reset(seed=k, options={'scene_index': si})
        ret = 0.0
        while True:
            obs, r, done, _, info = env.step(channel_pilot(obs))
            ret += r
            if done:
                break
        ss.append(info['sora_success'])
        R.append(ret)
print(f'{"kanal_pilotu":18s} SORA basari %{100 * np.mean(ss):5.1f}, odul {np.mean(R):6.1f}', flush=True)

from eland_rl.camera import rotation  # noqa: E402


def channel_pilot_level(obs):
    """Same pilot on a tilt-compensated image: the view rendered level at the (delayed) position,
    as an attitude-compensated warp of the label image would give on the vehicle."""
    pos, _ = env.veh.delayed_pose()
    sem, _ = env.cam.semantic_depth(env.scene, pos, rotation((0.0, 0.0, 1.0), env.veh.yaw))
    o = obs.copy()
    o[0] = sem.astype(np.float32) / 7
    return channel_pilot(o)


for name, pilot in (('kanal_pilotu_duz_goruntu', channel_pilot_level),):
    ss, R = [], []
    for si in range(len(scenes)):
        for k in range(15):
            obs, _ = env.reset(seed=k, options={'scene_index': si})
            ret = 0.0
            while True:
                obs, r, done, _, info = env.step(pilot(obs))
                ret += r
                if done:
                    break
            ss.append(info['sora_success'])
            R.append(ret)
    print(f'{name:18s} SORA basari %{100 * np.mean(ss):5.1f}, odul {np.mean(R):6.1f}', flush=True)
