"""Train the landing policy with PPO (docs/onkayit/rl_f0_onkayit.md section 4).

    python -m eland_rl.train --scenes list.txt --steps 500000 --seed 0 --out DIR [--binary]

Four parallel environments, SB3 PPO defaults, learning rate falling linearly
from 3e-4 to 0, ground-truth inputs. --reward picks a preset from env.REWARD_PRESETS;
--ent-coef adds PPO's entropy bonus (0 = SB3 default; amendment 4 uses 0.01). Writes DIR/model.zip, checkpoints, the
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

from .env import REWARD_PRESETS, EnvConfig, LandingEnv
from .policy import POLICY_KWARGS
from .scenes import load_list


def make_env(scene_list, rank, seed, out, binary, reward, obs='sem_depth'):
    def _f():
        env = LandingEnv(load_list(scene_list), EnvConfig(binary=binary, obs_mode=obs, **REWARD_PRESETS[reward]))
        env = Monitor(env, os.path.join(out, f'monitor_{rank}'),
                      info_keywords=('success', 'outcome', 'sora_success', 'majority_success'))
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
    ap.add_argument('--reward', default='paper', choices=sorted(REWARD_PRESETS))
    ap.add_argument('--obs', default='sem_depth', choices=['sem_depth', 'sem_depth_sora'])
    ap.add_argument('--ent-coef', type=float, default=0.0)
    ap.add_argument('--out', required=True)
    ap.add_argument('--device', default='auto')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    json.dump(vars(a), open(os.path.join(a.out, 'args.json'), 'w'), indent=1)

    venv = SubprocVecEnv([make_env(a.scenes, r, a.seed, a.out, a.binary, a.reward, a.obs) for r in range(a.envs)])
    lr0 = a.lr
    model = PPO('MlpPolicy', venv, learning_rate=lambda progress: lr0 * progress, policy_kwargs=POLICY_KWARGS,
                ent_coef=a.ent_coef, seed=a.seed, device=a.device, verbose=0)
    model.set_logger(configure(a.out, ['stdout', 'csv']))
    t0 = time.time()
    model.learn(total_timesteps=a.steps,
                callback=CheckpointCallback(max(a.steps // 10 // a.envs, 1), os.path.join(a.out, 'ckpt'), 'model'))
    model.save(os.path.join(a.out, 'model.zip'))
    venv.close()
    print(f'egitim bitti: {a.steps} adim, {(time.time() - t0) / 60:.1f} dk -> {a.out}/model.zip')


if __name__ == '__main__':
    main()
