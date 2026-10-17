"""Train the landing policy with PPO (docs/onkayit/rl_f0_onkayit.md section 4).

    python -m eland_rl.train --scenes list.txt --steps 500000 --seed 0 --out DIR [--binary]

Four parallel environments, SB3 PPO defaults, learning rate falling linearly
from 3e-4 to 0, ground-truth inputs. --reward picks a preset from env.REWARD_PRESETS;
--ent-coef adds PPO's entropy bonus (0 = SB3 default; amendment 4 uses 0.01). Writes DIR/model.zip, checkpoints, the
SB3 progress.csv and per-episode monitor files (reward, length, outcome).
--resume CKPT continues a checkpoint up to --steps in total; its logs go to DIR/devam<N>/ and
DIR/monitor_devam<N>_*, so the files of the first part stay as they are.
"""
import argparse
import json
import os
import time

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.logger import configure
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from .env import REWARD_PRESETS, ZEMIN_REWARDS, EnvConfig, LandingEnv
from .policy import ENCODERS, POLICY_KWARGS, policy_kwargs
from .scenes import load_list


def make_env(scene_list, rank, seed, out, binary, reward, obs='sem_depth', n_envs=1, cell=0.1, shard=False, extra=None,
             mon='monitor'):
    def _f():
        scenes = load_list(scene_list, shard=(rank, n_envs) if shard else None, dist_cell_m=cell)
        env = LandingEnv(scenes, EnvConfig(binary=binary, obs_mode=obs, **(extra or {}), **REWARD_PRESETS[reward]))
        env = Monitor(env, os.path.join(out, f'{mon}_{rank}'),
                      info_keywords=('success', 'outcome', 'sora_success', 'majority_success', 'zemin_success',
                                     'soft_landing', 'landing_class'))
        env.reset(seed=seed + 1000 * rank)
        return env
    return _f


def zemin_extra(a):
    """Amendment 9 switches; empty for the earlier runs, so their configuration is unchanged."""
    extra = {}
    if a.mirror:
        extra['mirror'] = True
    if a.reward == 'zemin_v1':
        extra['sora_metric'] = False        # training needs no 3 m grid; evaluation keeps the metric
        if a.land_hard is not None:
            extra['land_rewards'] = {**ZEMIN_REWARDS, 1: a.land_hard}
    return extra


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
    ap.add_argument('--sora-cell', type=float, default=0.1)
    ap.add_argument('--sem-source', default='gt', choices=['gt', 'pred'])
    ap.add_argument('--depth-mode', default='flat', choices=['flat', 'elev'])
    ap.add_argument('--sora-elev-tau', type=float, default=-1.0)
    ap.add_argument('--shield-train-m', type=float, default=-1.0,
                    help='>= 0: SORA shield inside the environment (amendment 8)')
    ap.add_argument('--shard', action='store_true', help='split the scene list over the environments')
    ap.add_argument('--vec', default='subproc', choices=['subproc', 'dummy'],
                    help='dummy: the environments share one process (same data, ~2 GB less memory)')
    ap.add_argument('--ent-coef', type=float, default=0.0)
    ap.add_argument('--out', required=True)
    ap.add_argument('--device', default='auto')
    ap.add_argument('--resume', default='', help='checkpoint zip to continue from (e.g. after the host slept)')
    ap.add_argument('--mirror', action='store_true', help='amendment 9: mirror the scene in half the episodes')
    ap.add_argument('--encoder', default='paper', choices=sorted(ENCODERS), help='amendment 10: policy trunk')
    ap.add_argument('--land-hard', type=float, default=None, help='zemin_v1: reward for landing on hard ground')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    lr0 = a.lr
    schedule = lambda progress: lr0 * progress  # noqa: E731
    done, tag, log_dir, mon = 0, '', a.out, 'monitor'
    if a.resume:
        # weights, optimiser state and the step counter come back; the rollout buffer and the episodes restart
        model = PPO.load(a.resume, device=a.device, custom_objects={'learning_rate': schedule, 'lr_schedule': schedule})
        done = model.num_timesteps
        tag = f'_devam{done}'
        log_dir, mon = os.path.join(a.out, f'devam{done}'), f'monitor_devam{done}'
    json.dump(vars(a), open(os.path.join(a.out, f'args{tag}.json'), 'w'), indent=1)

    venv_cls = DummyVecEnv if a.vec == 'dummy' else SubprocVecEnv
    venv = venv_cls([make_env(a.scenes, r, a.seed + done, a.out, a.binary, a.reward, a.obs, a.envs, a.sora_cell, a.shard,
                                   dict(sem_source=a.sem_source, depth_mode=a.depth_mode,
                                        sora_elev_tau=a.sora_elev_tau, shield_m=a.shield_train_m,
                                        **zemin_extra(a)), mon)
                     for r in range(a.envs)])
    if a.resume:
        model.set_env(venv)
    else:
        kw = POLICY_KWARGS if a.encoder == 'paper' else policy_kwargs(a.encoder)
        model = PPO('MlpPolicy', venv, learning_rate=schedule, policy_kwargs=kw,
                    ent_coef=a.ent_coef, seed=a.seed, device=a.device, verbose=0)
    model.set_logger(configure(log_dir, ['stdout', 'csv']))
    t0 = time.time()
    # reset_num_timesteps=False keeps the LR schedule on the total: progress = 1 - steps_done / a.steps
    model.learn(total_timesteps=a.steps - done, reset_num_timesteps=not a.resume,
                callback=CheckpointCallback(max(a.steps // 10 // a.envs, 1), os.path.join(a.out, 'ckpt'), 'model'))
    model.save(os.path.join(a.out, 'model.zip'))
    venv.close()
    print(f'egitim bitti: {a.steps} adim ({done} devralindi), {(time.time() - t0) / 60:.1f} dk -> {a.out}/model.zip')


if __name__ == '__main__':
    main()
