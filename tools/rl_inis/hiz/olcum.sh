#!/bin/bash
# eski/yeni ortam adimi: sirayla 4 tur, her ayar icin en iyi tur (arkada egitimler kosarken)
source $HOME/rl_inis/ortam.sh
H=$HOME/rl_inis/hiz
cd /tmp
for tur in 1 2 3 4; do for V in eski yeni; do
PYTHONPATH=$H/$V:$PYTHONPATH $RL_PY -c "
import time, numpy as np
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list
sc = load_list('$H/liste.txt', dist_cell_m=0.25)
for ad, ek in (('A1', {}), ('PD', dict(sem_source='pred', depth_mode='elev', sora_elev_tau=0.12))):
    env = LandingEnv(sc, EnvConfig(obs_mode='sem_depth_sora', **ek, **REWARD_PRESETS['sora_v1']))
    rng = np.random.default_rng(0); env.reset(seed=0); t = time.perf_counter()
    for _ in range(1500):
        _, _, d, _, _ = env.step(9 if rng.random() < 0.55 else int(rng.integers(0, 9)))
        if d: env.reset()
    print('$V', ad, round((time.perf_counter() - t) / 1.5, 3))
"
done; done | awk '{k=$1" "$2; if (!(k in m) || $3 < m[k]) m[k]=$3} END {for (k in m) print k, m[k], "ms/adim (en iyi)"}' | sort
echo "== birim testler (yeni)"
cd $HOME/ros2_ws/src/eland_rl && PYTHONPATH=$H/yeni:$PYTHONPATH $RL_PY -m pytest -q -p no:cacheprovider test 2>&1 | tail -2
