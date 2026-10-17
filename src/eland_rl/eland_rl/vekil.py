"""Proxy task (amendment 10): predict the view oracle's action from the observation.

A cheap screen of policy encoders before PPO: the same data, the same budget, three seeds, scored on
scenes no training sample came from. The oracle decides with the privileged ground truth; the encoder
sees only the observation, so the accuracy says how much of the decision an encoder can read from the
image. A good proxy score does not promise a good PPO policy -- the best encoders still go to PPO.

    python -m eland_rl.vekil --train LIST --val LIST --out DIR [--n-train 20000] [--n-val 4000]
"""
import argparse
import json
import os
import time

import gymnasium as gym
import numpy as np
import torch
from torch import nn

from .env import REWARD_PRESETS, EnvConfig, LandingEnv
from .pilots import view_oracle
from .policy import ENCODERS
from .scenes import load_list

SPACE = gym.spaces.Box(0.0, 1.0, (3, 128, 128), np.float32)


def collect(scenes, n, seed, reward):
    """n observations from random starts (5..30 m) and the oracle's action there, stored compactly."""
    env = LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', start_h=(5.0, 30.0), **REWARD_PRESETS[reward]))
    cls = np.empty((n, 128, 128), np.uint8)
    dep = np.empty((n, 128, 128), np.uint8)
    msk = np.empty((n, 128, 128), np.uint8)
    act = np.empty(n, np.int64)
    for i in range(n):
        obs, _ = env.reset(seed=seed * 1_000_000 + i)
        cls[i] = np.round(obs[0] * 7)
        dep[i] = np.round(obs[1] * 255)      # depth quantised to 40/255 m for storage
        msk[i] = obs[2] > 0.5
        act[i] = view_oracle(env)
    return cls, dep, msk, act


def as_obs(cls, dep, msk, idx, device):
    c = torch.as_tensor(cls[idx], device=device).float() / 7
    d = torch.as_tensor(dep[idx], device=device).float() / 255
    m = torch.as_tensor(msk[idx], device=device).float()
    return torch.stack([c, d, m], 1)


def balanced_accuracy(pred, true):
    rec = [float((pred[true == k] == k).mean()) for k in np.unique(true)]
    return float(np.mean(rec))


def run(name, seed, train, val, epochs, device, batch=256):
    torch.manual_seed(seed)
    np.random.seed(seed)
    cls_, dim = ENCODERS[name]
    model = nn.Sequential(cls_(SPACE, dim), nn.Linear(dim, 10)).to(device)
    params = sum(p.numel() for p in model.parameters())
    opt = torch.optim.Adam(model.parameters(), lr=3e-4)
    n = len(train[3])
    t0 = time.time()
    for _ in range(epochs):
        order = np.random.permutation(n)
        model.train()
        for b in range(0, n, batch):
            idx = order[b:b + batch]
            x = as_obs(*train[:3], idx, device)
            y = torch.as_tensor(train[3][idx], device=device)
            loss = nn.functional.cross_entropy(model(x), y)
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for b in range(0, len(val[3]), 512):
            idx = np.arange(b, min(b + 512, len(val[3])))
            preds.append(model(as_obs(*val[:3], idx, device)).argmax(1).cpu().numpy())
    pred = np.concatenate(preds)
    true = val[3]
    return dict(encoder=name, seed=seed, params=params, train_s=round(time.time() - t0, 1),
                acc=float((pred == true).mean()), bal_acc=balanced_accuracy(pred, true),
                descend_acc=float(((pred == 9) == (true == 9)).mean()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--train', required=True)
    ap.add_argument('--val', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--reward', default='zemin_v1')
    ap.add_argument('--n-train', type=int, default=20000)
    ap.add_argument('--n-val', type=int, default=4000)
    ap.add_argument('--epochs', type=int, default=6)
    ap.add_argument('--seeds', default='0,1,2')
    ap.add_argument('--encoders', default=','.join(ENCODERS))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    t0 = time.time()
    train = collect(load_list(a.train, dist_cell_m=0.25), a.n_train, 1, a.reward)
    val = collect(load_list(a.val, dist_cell_m=0.25), a.n_val, 2, a.reward)
    counts = np.bincount(val[3], minlength=10)
    print(f'veri: {a.n_train} egitim + {a.n_val} dogrulama gozlemi, {time.time() - t0:.0f} s; '
          f'dogrulamada kahin eylemleri {counts.tolist()} (cogunluk sinifi %{100 * counts.max() / counts.sum():.1f})', flush=True)
    rows = []
    for name in a.encoders.split(','):
        for seed in map(int, a.seeds.split(',')):
            r = run(name, seed, train, val, a.epochs, device)
            rows.append(r)
            print(json.dumps(r), flush=True)
    json.dump(rows, open(os.path.join(a.out, 'vekil.json'), 'w'), indent=1)
    print('\nkodlayici       parametre   dogruluk          dengeli dogruluk   alcal/alcalma')
    for name in a.encoders.split(','):
        r = [x for x in rows if x['encoder'] == name]
        f = lambda k: f"{100 * np.mean([x[k] for x in r]):5.1f} +- {100 * np.std([x[k] for x in r]):4.1f}"  # noqa: E731
        print(f"{name:14s} {r[0]['params']:10,d}   {f('acc')}     {f('bal_acc')}      {f('descend_acc')}")


if __name__ == '__main__':
    main()
