#!/bin/bash
# policy_node degisikligi icin kuru deneme: egitim yapilandirmasi okunuyor mu, gozlem kanallari dogru mu
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
source ~/rl_inis/ortam.sh
$RL_PY - <<'PY'
import numpy as np
from eland_rl.policy_node import PolicyNode
from eland_rl.camera import sora_channel
for run in ('messi_a1_s0', 'b_B0_s0', 'b_B2_s0'):
    cfg, note = PolicyNode.training_config(f'/home/arda/rl_inis/kos/{run}/args.json')
    print(run, '->', note, '| binary', cfg.binary)
# A1 (sora_v1): third channel must equal the old call
sem = np.random.default_rng(0).integers(0, 8, (128, 128)).astype(np.uint8)
cfg, _ = PolicyNode.training_config('/home/arda/rl_inis/kos/messi_a1_s0/args.json')
eski = sora_channel(sem, 20.0)
yeni = sora_channel(sem, 20.0, cfg.sora_m)
print('A1 ucuncu kanal eskisiyle ayni:', bool(np.array_equal(eski, yeni)))
PY
