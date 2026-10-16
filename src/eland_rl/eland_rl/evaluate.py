"""Evaluate policies on fixed starts in the light environment (paper Table I layout).

    python -m eland_rl.evaluate --scenes list.txt --model DIR/model.zip --starts 15 --out DIR/eval.csv

Every method flies the same starts: per scene, start k comes from reset(seed=k).
Tests use max_t 30 s and the measured nominal dynamics, not randomised
(docs/onkayit/rl_f0_onkayit.md sections 2.5 and 5). Methods: the policy
(deterministic), straight descent, uniform random actions.
"""
import argparse
import collections
import csv

import numpy as np

from .env import EnvConfig, LandingEnv
from .scenes import load_list


def run(env, act, scene_index, k):
    obs, info = env.reset(seed=k, options={'scene_index': scene_index})
    hist = collections.Counter()
    while True:
        a = act(obs)
        hist[a] += 1
        obs, _, done, trunc, info = env.step(a)
        if done or trunc:
            return info, hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenes', required=True)
    ap.add_argument('--model', default=None)
    ap.add_argument('--starts', type=int, default=15)
    ap.add_argument('--binary', action='store_true')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    scenes = load_list(a.scenes)
    env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, binary=a.binary))
    rng = np.random.default_rng(12345)
    methods = {'duz_inis': lambda o: 9, 'rastgele': lambda o: int(rng.integers(10))}
    if a.model:
        from stable_baselines3 import PPO
        model = PPO.load(a.model, device='cpu')
        methods = {'rl': lambda o: int(model.predict(o, deterministic=True)[0]), **methods}
    rows, hists = [], collections.defaultdict(collections.Counter)
    for name, act in methods.items():
        for i, sc in enumerate(scenes):
            for k in range(a.starts):
                info, h = run(env, act, i, k)
                hists[name].update(h)
                rows.append(dict(method=name, scene=sc.name, start=k, outcome=info['outcome'],
                                 success=int(info['success']), t=round(info['t'], 2), sora_ok=int(info['sora_ok']),
                                 sora_m=round(min(info['sora_distance_m'], 999.0), 2)))
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(scenes)} sahne x {a.starts} baslangic; max_t 30 s; nominal dinamik')
    for name in methods:
        r = [x for x in rows if x['method'] == name]
        ok = [x for x in r if x['success']]
        ts = np.array([x['t'] for x in ok])
        oc = collections.Counter(x['outcome'] for x in r)
        print(f'{name:9s} basari {100 * len(ok) / len(r):5.1f} %  SORA uyumlu {100 * np.mean([x["sora_ok"] for x in r]):5.1f} %  '
              f'sure {ts.mean() if len(ts) else float("nan"):5.1f} +- {ts.std() if len(ts) else float("nan"):4.1f} s  '
              f'{dict(oc)}')
        for sc in scenes:
            rs = [x for x in r if x['scene'] == sc.name]
            print(f'    {sc.name}: {sum(x["success"] for x in rs)}/{len(rs)}')
        h = hists[name]
        tot = sum(h.values())
        print(f'    eylemler: dur {h[0] / tot:.2f}, yanal {sum(h[i] for i in range(1, 9)) / tot:.2f}, alcal {h[9] / tot:.2f}')


if __name__ == '__main__':
    main()
