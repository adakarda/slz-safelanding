#!/bin/bash
source $HOME/rl_inis/ortam.sh
H=$HOME/rl_inis/hiz
S=$HOME/ros2_ws/src/eland_rl/eland_rl
cd $HOME/ros2_ws
git diff --quiet -- src/eland_rl || { echo "src temiz degil, cikiyorum"; exit 1; }
$RL_PY $H/yama_hiz.py $S && $RL_PY $H/yama_hiz2.py $S
diff -r --exclude=__pycache__ $H/yeni/eland_rl $S && echo "src = dogrulanan kopya"
cd $HOME/ros2_ws/src/eland_rl && $RL_PY -m pytest -q -p no:cacheprovider test 2>&1 | tail -2
cd $HOME/ros2_ws && git diff --stat
