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

from .env import REWARD_PRESETS, ZEMIN_REWARDS, EnvConfig, LandingEnv
from .scenes import load_list


def run(env, act, scene_index, k):
    obs, info = env.reset(seed=k, options={'scene_index': scene_index})
    hist = collections.Counter()
    ret = 0.0
    while True:
        a = act(obs)
        hist[a] += 1
        obs, r, done, trunc, info = env.step(a)
        ret += r
        if done or trunc:
            return info, hist, ret


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenes', required=True)
    ap.add_argument('--model', default=None)
    ap.add_argument('--starts', type=int, default=15)
    ap.add_argument('--binary', action='store_true')
    ap.add_argument('--reward', default='paper', choices=sorted(REWARD_PRESETS))
    ap.add_argument('--obs', default='sem_depth', choices=['sem_depth', 'sem_depth_sora'])
    ap.add_argument('--sora-cell', type=float, default=0.1)
    ap.add_argument('--sem-source', default='gt', choices=['gt', 'pred'])
    ap.add_argument('--depth-mode', default='flat', choices=['flat', 'elev'])
    ap.add_argument('--sora-elev-tau', type=float, default=-1.0)
    ap.add_argument('--shield-train-m', type=float, default=-1.0,
                    help='>= 0: SORA shield inside the environment (amendment 8)')
    ap.add_argument('--shield-m', type=float, default=10.0)
    ap.add_argument('--oracle', action='store_true', help='add the view oracle (privileged GT upper bound)')
    ap.add_argument('--land-hard', type=float, default=None, help='zemin_v1: reward for landing on hard ground')
    ap.add_argument('--diag', action='store_true', help='amendment 13: the model has the sliding-descent actions')
    ap.add_argument('--only-rl', action='store_true', help='amendment 15: evaluate only rl and rl_kalkan')
    ap.add_argument('--kanallar', default='', help='amendment 16: the model\'s extra observation channels')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    scenes = load_list(a.scenes, dist_cell_m=a.sora_cell)
    env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, binary=a.binary, obs_mode=a.obs, sem_source=a.sem_source,
                                       depth_mode=a.depth_mode, sora_elev_tau=a.sora_elev_tau,
                                       shield_m=a.shield_train_m, diag_actions=a.diag,
                                       kanallar=tuple(k for k in a.kanallar.split(',') if k),
                                       **{**REWARD_PRESETS[a.reward],
                                          **({'land_rewards': {**ZEMIN_REWARDS, 1: a.land_hard}}
                                             if a.land_hard is not None else {})}))
    rng = np.random.default_rng(12345)
    methods = {'duz_inis': lambda o: 9, 'rastgele': lambda o: int(rng.integers(10))}
    if a.obs == 'sem_depth_sora':
        from .pilots import channel_pilot, shield as _shield
        methods['kanal'] = channel_pilot
        # amendment 9: straight descent behind the same shield, the rule baseline RL + shield must beat
        methods['duz_kalkan'] = lambda o: _shield(9, o, env.veh.delayed_pose()[0][2], a.shield_m)[0]
    if a.oracle:
        from .pilots import view_oracle
        methods['gorus_kahini'] = lambda o: view_oracle(env)
    if a.model:
        from stable_baselines3 import PPO
        model = PPO.load(a.model, device='cpu')
        rl = lambda o: int(model.predict(o, deterministic=True)[0])  # noqa: E731
        methods = {'rl': rl, **methods}
        if a.obs == 'sem_depth_sora':
            from .pilots import shield

            def rl_shield(o):
                return shield(rl(o), o, env.veh.delayed_pose()[0][2], a.shield_m)[0]
            methods = {'rl': rl, 'rl_kalkan': rl_shield, **{k: v for k, v in methods.items() if k != 'rl'}}
        if a.only_rl:                       # amendment 15 screening: the baselines do not change between models
            methods = {k: v for k, v in methods.items() if k in ('rl', 'rl_kalkan')}
    rows, hists = [], collections.defaultdict(collections.Counter)
    for name, act in methods.items():
        for i, sc in enumerate(scenes):
            for k in range(a.starts):
                info, h, ret = run(env, act, i, k)
                hists[name].update(h)
                rows.append(dict(method=name, scene=sc.name, start=k, outcome=info['outcome'],
                                 success=int(info['success']), t=round(info['t'], 2), sora_ok=int(info['sora_ok']),
                                 sora_success=int(info['sora_success']), majority_success=int(info['majority_success']),
                                 ret=round(ret, 2),
                                 sora_m=round(min(info['sora_distance_m'], 999.0), 2),
                                 landing_class=info['landing_class'], zemin_success=int(info['zemin_success']),
                                 soft=int(info['soft_landing'])))
    with open(a.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'{len(scenes)} sahne x {a.starts} baslangic; max_t 30 s; nominal dinamik; odul {a.reward}')
    for name in methods:
        r = [x for x in rows if x['method'] == name]
        ok = [x for x in r if x['success']]
        ts = np.array([x['t'] for x in ok])
        oc = collections.Counter(x['outcome'] for x in r)
        print(f'{name:10s} SORA basari {100 * np.mean([x["sora_success"] for x in r]):5.1f} %  '
              f'cogunluk basari {100 * np.mean([x["majority_success"] for x in r]):5.1f} %  '
              f'odul {np.mean([x["ret"] for x in r]):6.1f}  '
              f'(secili kural basari {100 * len(ok) / len(r):5.1f} %, eski SORA uyumlu {100 * np.mean([x["sora_ok"] for x in r]):5.1f} %)  '
              f'sure {ts.mean() if len(ts) else float("nan"):5.1f} +- {ts.std() if len(ts) else float("nan"):4.1f} s  '
              f'{dict(oc)}')
        for sc in scenes:
            rs = [x for x in r if x['scene'] == sc.name]
            print(f'    {sc.name}: {sum(x["success"] for x in rs)}/{len(rs)}')
        h = hists[name]
        tot = sum(h.values())
        print(f'    eylemler: dur {h[0] / tot:.2f}, yanal {sum(h[i] for i in range(1, 9)) / tot:.2f}, alcal {h[9] / tot:.2f}')
        lc = collections.Counter(x['landing_class'] for x in r if x['landing_class'] >= 0)
        print(f'    zemin basari {100 * np.mean([x["zemin_success"] for x in r]):5.1f} %  '
              f'yumusak {100 * np.mean([x["soft"] for x in r]):5.1f} %  inis sinifi {dict(sorted(lc.items()))}')


if __name__ == '__main__':
    main()
