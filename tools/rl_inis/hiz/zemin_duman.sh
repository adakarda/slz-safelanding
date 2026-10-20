#!/bin/bash
# zemin_v1 + ayna: kisa egitim ve degerlendirme duman testi
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; O=/tmp/zemin_duman; rm -rf $O
head -4 $D/train_b.txt > /tmp/zd_train.txt; head -2 $D/val_b.txt > /tmp/zd_val.txt
cd $HOME/rl_inis
$RL_PY -u -m eland_rl.train --scenes /tmp/zd_train.txt --shard --sora-cell 0.25 --steps 4096 --envs 2 --vec dummy \
	--reward zemin_v1 --mirror --ent-coef 0.01 --obs sem_depth_sora --out $O > $O.log 2>&1 || { tail -15 $O.log; exit 1; }
tail -1 $O.log; head -2 $O/monitor_0.monitor.csv
$RL_PY -u -m eland_rl.evaluate --scenes /tmp/zd_val.txt --sora-cell 0.25 --model $O/model.zip --starts 2 \
	--reward zemin_v1 --obs sem_depth_sora --oracle --out $O/eval.csv 2>&1 | grep -v -i warn | grep -vE "^    (trainval|eylemler)"
head -2 $O/eval.csv
