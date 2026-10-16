"""Train the landing policy with PPO (docs/onkayit/rl_f0_onkayit.md section 4).

    python -m eland_rl.train --scenes list.txt --steps 500000 --seed 0 --out DIR [--binary]

Four parallel environments, SB3 PPO defaults, learning rate falling linearly
from 3e-4 to 0, ground-truth inputs. Writes DIR/model.zip, checkpoints, the
SB3 progress.csv and per-episode monitor files (reward, length, outcome).
"""
import argparse
import json
import os
import time

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import SubprocVecEnv

from .env import EnvConfig, LandingEnv
from .policy import POLICY_KWARGS
from .scenes import load_list


def make_env(scene_list, rank, seed, out, binary):
    def _f():
        env = LandingEnv(load_list(scene_list), EnvConfig(binary=binary))
        env = Monitor(env, os.path.join(out, f'monitor_{rank}'), info_keywords=('success', 'outcome', 'sora_ok'))
        env.reset(seed=seed + 1000 * rank)
        return env
    return _f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenes', required=True)
    ap.add_argument('--steps', type=int, default=500_000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--envs', type=int, default=4)
    ap.add_argument('--lr', type=float, default=3e-4)
    ap.add_argument('--binary', action='store_true')
    ap.add_argument('--out', required=True)
    ap.add_argument('--device', default='auto')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    json.dump(vars(a), open(os.path.join(a.out, 'args.json'), 'w'), indent=1)

    venv = SubprocVecEnv([make_env(a.scenes, r, a.seed, a.out, a.binary) for r in range(a.envs)])
    lr0 = a.lr
    model = PPO('MlpPolicy', venv, learning_rate=lambda progress: lr0 * progress, policy_kwargs=POLICY_KWARGS,
                seed=a.seed, device=a.device, verbose=0)
    model.set_logger(configure(a.out, ['stdout', 'csv']))
    t0 = time.time()
    model.learn(total_timesteps=a.steps,
                callback=CheckpointCallback(max(a.steps // 10 // a.envs, 1), os.path.join(a.out, 'ckpt'), 'model'))
    model.save(os.path.join(a.out, 'model.zip'))
    venv.close()
    print(f'egitim bitti: {a.steps} adim, {(time.time() - t0) / 60:.1f} dk -> {a.out}/model.zip')


if __name__ == '__main__':
    main()
