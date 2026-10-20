#!/bin/bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
python3 ~/rl_inis/airsim_pilot/faz3_kare.py "${1:-/mnt/c/Users/arda_/airsim/faz3_kareler}"
PYTHONPATH=~/ros2_ws/src/eland_airsim:$PYTHONPATH ~/airsim-venv/bin/python - <<'PY'
from eland_airsim import istemci
c = istemci.connect(timeout_s=5)
k = c.simGetGroundTruthKinematics()
p, v = k.position, k.linear_velocity
print(f'NED x {p.x_val:.2f} y {p.y_val:.2f} z {p.z_val:.2f}  hiz {v.x_val:.2f} {v.y_val:.2f} {v.z_val:.2f}')
PY
