"""Command audit data: replay the policy in the light environment and judge each command against SORA.

For every step: what the policy saw (128x128 classes), the command it chose,
the camera footprint on the photo, the ground point at the exact image centre,
whether that point is SORA-safe (landable class AND >= 3 m from structure /
water / vehicle / person), and what a simple SORA rule would have commanded:

    centre SORA-safe       -> descend
    otherwise              -> lateral, towards the nearest SORA-safe point
                              (quantised to the 8 body-relative directions)

The rule is a transparent reference to question the policy with, not the
optimum. Verdicts: ok / dikkat / hata (see verdict()).

    python veri.py <scenes.txt> <model.zip> <starts_per_scene> <out.json>
"""
import base64
import json
import math
import sys

import cv2
import numpy as np
from eland_common import classes
from eland_rl.camera import body_rays, ground_hits
from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scenes import load_list

SORA_M = 3.0
CELL = 0.1
COLOURS = np.array([classes.CLASS_COLORS[i] for i in range(8)], np.uint8)
NAMES = ['dur', 'ileri', 'sol-ileri', 'sol', 'sol-geri', 'geri', 'sag-geri', 'sag', 'sag-ileri', 'alcal']
CORNERS = body_rays(320, 240, cols=np.array([0, 319]), rows=np.array([0, 239]))   # 2x2x3


def b64(img, ext, **kw):
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    ok, buf = cv2.imencode(ext, img, [cv2.IMWRITE_JPEG_QUALITY, 80] if ext == '.jpg' else [])
    return ('data:image/jpeg;base64,' if ext == '.jpg' else 'data:image/png;base64,') + base64.b64encode(buf).decode()


class SoraMap:
    def __init__(self, scene):
        self.sc = scene
        scene.hazard_distance(0.0, 0.0)                    # builds scene._dist on the CELL grid
        gh, gw = scene._dist.shape
        landable = np.isin(scene.mask, list(classes.DEFAULT_SAFE_CLASSES)).astype(np.float32)
        landable = cv2.resize(landable, (gw, gh), interpolation=cv2.INTER_AREA) > 0.999
        self.safe = landable & (scene._dist >= SORA_M)
        self.landable = landable
        # nearest SORA-safe cell for every cell: label of the nearest zero pixel -> its coordinates
        src = (~self.safe).astype(np.uint8)
        self.gw, self.gh = gw, gh
        if self.safe.any():
            _, lab = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
            ys, xs = np.nonzero(src == 0)
            lut = np.zeros((lab.max() + 1, 2), np.int32)
            lut[lab[ys, xs]] = np.stack([ys, xs], 1)
            near = lut[lab]
            self.iy, self.ix = near[..., 0], near[..., 1]
        else:
            self.iy = np.full((gh, gw), gh // 2, np.int32)
            self.ix = np.full((gh, gw), gw // 2, np.int32)

    def cell(self, x, y):
        u = int(np.clip((x / self.sc.size[0] + 0.5) * self.gw, 0, self.gw - 1))
        v = int(np.clip((0.5 - y / self.sc.size[1]) * self.gh, 0, self.gh - 1))
        return v, u

    def is_safe(self, x, y):
        return bool(self.safe[self.cell(x, y)])

    def nearest_safe(self, x, y):
        v, u = self.cell(x, y)
        tv, tu = self.iy[v, u], self.ix[v, u]
        return ((tu + 0.5) / self.gw - 0.5) * self.sc.size[0], (0.5 - (tv + 0.5) / self.gh) * self.sc.size[1]

    def image(self, width):
        h = int(round(width * self.gh / self.gw))
        img = np.zeros((self.gh, self.gw, 4), np.uint8)
        img[self.landable & ~self.safe] = (240, 150, 30, 150)      # landable class but < 3 m from a hazard
        img[self.safe] = (60, 200, 90, 150)                        # SORA-safe
        img[~self.landable] = (0, 0, 0, 90)
        img = cv2.resize(img, (width, h), interpolation=cv2.INTER_NEAREST)
        ok, buf = cv2.imencode('.png', cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA))
        return 'data:image/png;base64,' + base64.b64encode(buf).decode()


def angdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def verdict(a, centre_safe, alt, act_world_deg, rule_world_deg):
    if a == 9:
        if centre_safe:
            return 'ok', 'SORA-güvenli noktaya alçalıyor'
        return ('dikkat', 'orta SORA-güvenli değil, ama hâlâ yüksekte (düzeltme şansı var)') if alt > 10.0 else \
            ('hata', '10 m altında, SORA-güvenli olmayan noktaya alçalıyor')
    if a == 0:
        return 'dikkat', 'duruyor (zaman kaybı)'
    if centre_safe:
        return 'dikkat', 'orta zaten SORA-güvenli, yine de kayıyor'
    d = angdiff(act_world_deg, rule_world_deg)
    if d <= 45.0:
        return 'ok', f'en yakın güvenli noktaya doğru (sapma {d:.0f}°)'
    if d <= 90.0:
        return 'dikkat', f'güvenli noktaya kısmen doğru (sapma {d:.0f}°)'
    return 'hata', f'güvenli noktadan uzaklaşıyor (sapma {d:.0f}°)'


def main(scene_list, model_path, n_starts, out):
    from stable_baselines3 import PPO
    import os
    from eland_rl.env import REWARD_PRESETS
    scenes = load_list(scene_list, load_photo=True)
    model = PPO.load(model_path, device='cpu')
    # the model's own training settings: reward preset and observation mode
    args_path = os.path.join(os.path.dirname(os.path.dirname(model_path)) if '/ckpt/' in model_path
                             else os.path.dirname(model_path), 'args.json')
    targs = json.load(open(args_path)) if os.path.exists(args_path) else {}
    reward = targs.get('reward', 'paper')
    obs_mode = 'sem_depth_sora' if int(model.observation_space.shape[0]) == 3 else 'sem_depth'
    env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode=obs_mode,
                                       **REWARD_PRESETS[reward]))
    print(f'odul {reward}, gozlem {obs_mode}')
    data = {'model': model_path, 'reward': reward, 'obs_mode': obs_mode, 'sora_m': SORA_M, 'names': NAMES,
            'scenes': [], 'episodes': []}
    for si, sc in enumerate(scenes):
        sm = SoraMap(sc)
        W = 1000
        H = int(round(W * sc.photo.shape[0] / sc.photo.shape[1]))
        data['scenes'].append(dict(
            name=sc.name, size=list(sc.size), w=W, h=H,
            photo=b64(cv2.resize(sc.photo, (W, H), interpolation=cv2.INTER_AREA), '.jpg'),
            mask=b64(cv2.resize(COLOURS[sc.mask], (W, H), interpolation=cv2.INTER_NEAREST), '.png'),
            sora=sm.image(W)))
        for k in range(n_starts):
            obs, info = env.reset(seed=k, options={'scene_index': si})
            steps = []
            while True:
                pos, R = env.veh.delayed_pose()          # what the policy is looking at
                a = int(model.predict(obs, deterministic=True)[0])
                X, Y, t = ground_hits(np.array([[0.0, 0.0, -1.0]]), pos, R)
                cx, cy = float(X[0]), float(Y[0])
                cls = int(sc.classes_at(np.array([cx]), np.array([cy]))[0])
                hd = sc.hazard_distance(cx, cy)
                safe = sm.is_safe(cx, cy)
                tx, ty = sm.nearest_safe(cx, cy)
                yaw = math.degrees(env.veh.yaw)
                rule_deg = math.degrees(math.atan2(ty - cy, tx - cx))
                if safe:
                    rule_a = 9
                else:
                    rel = (rule_deg - yaw) % 360.0
                    rule_a = 1 + int(round(rel / 45.0)) % 8
                act_deg = (yaw + (a - 1) * 45.0) if 1 <= a <= 8 else None
                v, why = verdict(a, safe, float(pos[2]), act_deg if act_deg is not None else 0.0, rule_deg)
                FX, FY, _ = ground_hits(CORNERS, pos, R)
                corners = [[round(float(FX[i, j]), 2), round(float(FY[i, j]), 2)] for i, j in ((0, 0), (0, 1), (1, 1), (1, 0))]
                sem = np.round(obs[0] * 7).astype(np.uint8)
                steps.append(dict(
                    t=round(env.veh.t, 2), x=round(float(env.veh.pos[0]), 2), y=round(float(env.veh.pos[1]), 2),
                    px=round(float(pos[0]), 2), py=round(float(pos[1]), 2), z=round(float(pos[2]), 2),
                    yaw=round(yaw, 1), a=a, cx=round(cx, 2), cy=round(cy, 2), ccls=cls,
                    chaz=round(min(hd, 99.0), 2), csafe=safe, tx=round(tx, 2), ty=round(ty, 2), rule=rule_a,
                    share=round(float(np.isin(sem, [0, 1]).mean()), 3), v=v, why=why, fp=corners,
                    view=b64(cv2.resize(COLOURS[sem], (128, 128), interpolation=cv2.INTER_NEAREST), '.png')))
                obs, r, done, trunc, info = env.step(a)
                cfg = env.cfg
                r_t = 0.0 if done else cfg.r_step
                end = r - (cfg.w_t * r_t + cfg.w_s * info['r_s'] + cfg.w_c * info['r_c'] + cfg.w_a * info['r_a'])
                cum = (steps[-2]['cum'] if len(steps) > 1 else 0.0) + r
                steps[-1].update(r=round(r, 3), rt=round(cfg.w_t * r_t, 3), rs=round(cfg.w_s * info['r_s'], 3),
                                 ra=round(cfg.w_a * info['r_a'], 3), rc=round(cfg.w_c * info['r_c'], 3),
                                 rend=round(end, 2), cum=round(cum, 2))
                if done or trunc:
                    break
            n = len(steps)
            data['episodes'].append(dict(
                scene=si, start=k, outcome=info['outcome'], success=bool(info['success']),
                sora_ok=bool(info['sora_success']), sora_m=round(min(info['sora_distance_m'], 99.0), 2),
                t=round(info['t'], 2), landing=list(info['landing_xy']), total=steps[-1]['cum'],
                agree=round(sum(s['v'] == 'ok' for s in steps) / n, 3),
                wrong=round(sum(s['v'] == 'hata' for s in steps) / n, 3), steps=steps))
            print(f'{sc.name} b{k}: {info["outcome"]}, {n} adim, SORA kurali ile uyum '
                  f'{data["episodes"][-1]["agree"]:.2f}, hata {data["episodes"][-1]["wrong"]:.2f}', flush=True)
    json.dump(data, open(out, 'w'))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4])
