"""Data for the training explainer page: one scene, one training-style episode, learning snapshots,
training curves, and the measured PX4 response. Everything real, from the sora_v2_s0 run.

    python veri.py <out.json>
"""
import base64
import csv
import glob
import json
import math
import sys

import cv2
import numpy as np
import torch
from stable_baselines3 import PPO

from eland_common import classes
from eland_rl.camera import body_rays, ground_hits
from eland_rl.dynamics import DynamicsParams
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

RUN = '/home/arda/rl_inis/kos/sora_v2_s0'
SCENES = '/home/arda/rl_inis/sahneler_pilot.txt'
SI, START = 4, 1                                     # DJI_0332, start 1
COLOURS = np.array([classes.CLASS_COLORS[i] for i in range(8)], np.uint8)
CORNERS = body_rays(320, 240, cols=np.array([0, 319]), rows=np.array([0, 239]))


def b64(img, ext='.png', q=82):
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, q] if ext == '.jpg' else [])
    return ('data:image/jpeg;base64,' if ext == '.jpg' else 'data:image/png;base64,') + base64.b64encode(buf).decode()


def footprint(pos, R):
    X, Y, _ = ground_hits(CORNERS, pos, R)
    return [[round(float(X[i, j]), 2), round(float(Y[i, j]), 2)] for i, j in ((0, 0), (0, 1), (1, 1), (1, 0))]


out = {}
scenes = load_list(SCENES, load_photo=True)
sc = scenes[SI]
W = 900
H = int(round(W * sc.photo.shape[0] / sc.photo.shape[1]))
safe, dist, _ = sc._sora_grid(3.0)
gh, gw = safe.shape
landable = np.isin(sc.mask, [0, 1]).astype(np.float32)
landable = cv2.resize(landable, (gw, gh), interpolation=cv2.INTER_AREA) > 0.999
sora_img = np.zeros((gh, gw, 3), np.uint8)
sora_img[:] = (60, 60, 60)
sora_img[landable & ~safe] = (240, 150, 30)
sora_img[safe] = (60, 190, 90)
pay = np.bincount(sc.mask.ravel(), minlength=8) / sc.mask.size
out['scene'] = dict(
    name=sc.name, size=list(sc.size), w=W, h=H,
    photo=b64(cv2.resize(sc.photo, (W, H), interpolation=cv2.INTER_AREA), '.jpg'),
    mask=b64(cv2.resize(COLOURS[sc.mask], (W, H), interpolation=cv2.INTER_NEAREST)),
    sora=b64(cv2.resize(sora_img, (W, H), interpolation=cv2.INTER_NEAREST)),
    shares=[round(float(v), 4) for v in pay], sora_share=round(float(safe.mean()), 4),
    gsd_cm=round(100 * sc.size[0] / sc.mask.shape[1], 2), px=list(sc.mask.shape[::-1]))

# ---- one training-style episode: sampled actions, randomised dynamics, 90 s limit (as in training)
model = PPO.load(f'{RUN}/model.zip', device='cpu')
env = LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['sora_v1']))
torch.manual_seed(3)
obs, info = env.reset(seed=3, options={'scene_index': SI})
dyn = info['dynamics']
out['episode_dynamics'] = dict(tau_xy=round(dyn.tau_xy, 2), tau_z=round(dyn.tau_z, 2), a_max=round(dyn.a_max, 2),
                               cmd_delay_xy=round(dyn.cmd_delay_xy, 2), latency=round(dyn.latency_s, 2))
steps, cum = [], 0.0
while True:
    pos, R = env.veh.delayed_pose()
    with torch.no_grad():
        t_obs = torch.as_tensor(obs[None])
        probs = model.policy.get_distribution(t_obs).distribution.probs[0].numpy()
    a = int(np.random.default_rng(len(steps) + 11).choice(10, p=probs / probs.sum()))
    _, _, dsafe = sc.nearest_sora_safe(env.veh.pos[0], env.veh.pos[1])
    rec = dict(k=len(steps), t=round(env.veh.t, 2), x=round(float(env.veh.pos[0]), 2), y=round(float(env.veh.pos[1]), 2),
               z=round(float(env.veh.pos[2]), 2), yaw=round(math.degrees(env.veh.yaw), 1), a=a,
               p=[round(float(v), 4) for v in probs], dsafe=round(min(dsafe, 99.0), 2), fp=footprint(pos, R))
    if len(steps) % 4 == 0:
        sem = np.round(obs[0] * 7).astype(np.uint8)
        rec['v_sem'] = b64(cv2.resize(COLOURS[sem], (128, 128), interpolation=cv2.INTER_NEAREST))
        rec['v_dep'] = b64((obs[1] * 255).astype(np.uint8))
        ch = np.zeros((128, 128, 3), np.uint8)
        ch[:] = (50, 50, 50)
        ch[obs[2] > 0.5] = (60, 190, 90)
        rec['v_sora'] = b64(ch)
    obs, r, done, _, info = env.step(a)
    cfg = env.cfg
    r_t = 0.0 if done else cfg.r_step
    end = r - (cfg.w_t * r_t + cfg.w_s * info['r_s'] + cfg.w_c * info['r_c'] + cfg.w_a * info['r_a'] + info['r_shape'])
    cum += r
    rec.update(r=round(r, 3), rt=round(r_t, 3), rshape=round(info['r_shape'], 3), ra=round(info['r_a'], 3),
               rend=round(end, 2), cum=round(cum, 2))
    steps.append(rec)
    if done:
        break
out['episode'] = dict(steps=steps, outcome=info['outcome'], sora_success=bool(info['sora_success']),
                      t=round(info['t'], 2), landing=list(info['landing_xy']), total=round(cum, 2))
print('bolum:', info['outcome'], len(steps), 'adim, toplam', round(cum, 1))

# ---- learning snapshots: the same start, deterministic, at several checkpoints
eval_env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                        **REWARD_PRESETS['sora_v1']))
snaps = []
for ck in (100000, 300000, 600000, None):
    path = f'{RUN}/ckpt/model_{ck}_steps.zip' if ck else f'{RUN}/model.zip'
    m = PPO.load(path, device='cpu')
    o, _ = eval_env.reset(seed=START, options={'scene_index': SI})
    tr, acts = [], []
    while True:
        tr.append([round(float(eval_env.veh.pos[0]), 2), round(float(eval_env.veh.pos[1]), 2)])
        a = int(m.predict(o, deterministic=True)[0])
        acts.append(a)
        o, _, d, _, inf = eval_env.step(a)
        if d:
            break
    tr.append(list(inf['landing_xy']))
    snaps.append(dict(steps=ck or 1000000, path=tr, outcome=inf['outcome'], sora=bool(inf['sora_success']),
                      t=round(inf['t'], 1), lateral=sum(1 <= x <= 8 for x in acts), n=len(acts)))
    print('anlik', ck, inf['outcome'], round(inf['t'], 1))
out['snapshots'] = snaps

# ---- training curves: rolling SORA success of training episodes (sampled actions), for the three designs
def rolling(run, key):
    rows = []
    for f in glob.glob(f'/home/arda/rl_inis/kos/{run}/monitor_*.monitor.csv'):
        with open(f) as fh:
            next(fh)
            for r in csv.DictReader(fh):
                rows.append((float(r['t']), r.get(key, 'False') == 'True', float(r['l'])))
    rows.sort()
    steps = np.cumsum([r[2] for r in rows])
    ok = np.array([r[1] for r in rows], float)
    win = 400
    pts = []
    for i in range(win, len(rows), max(1, len(rows) // 120)):
        pts.append([int(steps[i]), round(float(ok[i - win:i].mean()), 4)])
    return pts


out['curves'] = {
    'sora_v2_s0': rolling('sora_v2_s0', 'sora_success'),
    'sora_v2_s1': rolling('sora_v2_s1', 'sora_success'),
    'sora_v1_s0': rolling('sora_v1_s0', 'sora_success'),
}
prog = list(csv.DictReader(open(f'{RUN}/progress.csv')))
out['entropy'] = [[int(p['time/total_timesteps']), round(-float(p['train/entropy_loss']), 3)]
                  for p in prog if p.get('train/entropy_loss')]
out['eplen'] = [[int(p['time/total_timesteps']), round(float(p['rollout/ep_len_mean']), 1)] for p in prog]

# ---- measured PX4 response (identification flight kos1): command vs velocity, first steps
d = np.load('/home/arda/rl_inis/tanilama/kos1.npz')
lp, sp = d['lp'][1:], d['sp']
t0 = sp[np.argmax(np.abs(sp[:, 1:]).sum(1) > 0), 0] - 1.0e6
sel = (lp[:, 0] >= t0) & (lp[:, 0] <= t0 + 9.0e6)
tl = (lp[sel, 0] - t0) * 1e-6
ts = (sp[:, 0] - t0) * 1e-6
cmd = np.interp(tl, ts, sp[:, 1], left=0.0)
cmd = np.array([sp[max(0, np.searchsorted(sp[:, 0], t, side='right') - 1), 1] for t in lp[sel, 0]])
q = d['att']
tilt = np.degrees(np.arccos(np.clip(1 - 2 * (np.interp(lp[sel, 0], q[:, 0], q[:, 2]) ** 2 + np.interp(lp[sel, 0], q[:, 0], q[:, 3]) ** 2), -1, 1)))
k = max(1, len(tl) // 180)
out['px4'] = dict(t=[round(float(v), 3) for v in tl[::k]], cmd=[round(float(v), 3) for v in cmd[::k]],
                  vel=[round(float(v), 3) for v in lp[sel, 4][::k]], tilt=[round(float(v), 2) for v in tilt[::k]])
json.dump(out, open(sys.argv[1], 'w'))
print('yazildi', sys.argv[1])
