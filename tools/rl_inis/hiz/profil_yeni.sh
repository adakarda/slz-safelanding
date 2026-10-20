#!/bin/bash
source $HOME/rl_inis/ortam.sh
H=$HOME/rl_inis/hiz
cd /tmp
PYTHONPATH=$H/yeni:$PYTHONPATH $RL_PY -c "
import cProfile, pstats, numpy as np
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list
sc = load_list('$H/liste.txt', dist_cell_m=0.25)
for ek in ({}, dict(sem_source='pred', depth_mode='elev', sora_elev_tau=0.12)):
    env = LandingEnv(sc, EnvConfig(obs_mode='sem_depth_sora', **ek, **REWARD_PRESETS['sora_v1']))
    rng = np.random.default_rng(0); env.reset(seed=0)
    pr = cProfile.Profile(); pr.enable()
    for _ in range(1500):
        _, _, d, _, _ = env.step(9 if rng.random() < 0.55 else int(rng.integers(0, 9)))
        if d: env.reset()
    pr.disable(); print('==', ek)
    pstats.Stats(pr).sort_stats('tottime').print_stats(14)
" 2>&1 | grep -E '==|function calls|^ +[0-9]' | cut -c1-150
