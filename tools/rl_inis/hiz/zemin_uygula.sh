#!/bin/bash
source $HOME/rl_inis/ortam.sh
H=$HOME/rl_inis/hiz; S=$HOME/ros2_ws/src/eland_rl
cd $HOME/ros2_ws
git diff --quiet -- src/eland_rl || { echo "src temiz degil, cikiyorum"; exit 1; }
$RL_PY $H/yama_zemin.py $S/eland_rl $S/test/test_env.py || exit 1
diff -r --exclude=__pycache__ $H/yeni/eland_rl $S/eland_rl && diff $H/yeni/test_env.py $S/test/test_env.py && echo "src = dogrulanan kopya"
cd $S && $RL_PY -m pytest -q -p no:cacheprovider test 2>&1 | tail -2
cd $HOME/ros2_ws && git diff --stat
# B deneyi listeleri (K75 dogrulama kumesi: 0004, 0043, Path B)
D=$HOME/eland_veri/rl/messi_ds4
grep -E "Descend__100_0004__|Descend__100_0043__|Path__B__" $D/train.txt > $D/val_b.txt
grep -vE "Descend__100_0004__|Descend__100_0043__|Path__B__" $D/train.txt > $D/train_b.txt
wc -l $D/train.txt $D/train_b.txt $D/val_b.txt
