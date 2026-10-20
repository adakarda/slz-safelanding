#!/bin/bash
# RL inis calisma ortami: venv + depodaki eland_rl ve eland_common kaynaktan.
#   source ~/rl_inis/ortam.sh
export PYTHONPATH=$HOME/ros2_ws/src/eland_rl:$HOME/ros2_ws/src/eland_common${PYTHONPATH:+:$PYTHONPATH}
export RL_PY=$HOME/rl_inis/venv/bin/python
