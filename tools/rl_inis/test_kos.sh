#!/bin/bash
# eland_rl birim testleri
source $HOME/rl_inis/ortam.sh
cd $HOME/ros2_ws/src/eland_rl && $RL_PY -m pytest -q -p no:cacheprovider test "$@" 2>&1 | tail -30
