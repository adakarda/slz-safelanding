#!/bin/bash
source $HOME/rl_inis/ortam.sh
AV=$(free -m | awk 'NR==2 {print $7}'); echo "mevcut MB: $AV"; [ "$AV" -lt 2000 ] && { echo "bellek az"; exit 1; }
D=$HOME/eland_veri/rl/messi_ds4
head -3 $D/train_b.txt > /tmp/vd_train.txt; head -2 $D/val_b32.txt > /tmp/vd_val.txt
cd /tmp && CUDA_VISIBLE_DEVICES= $RL_PY -m eland_rl.vekil --train /tmp/vd_train.txt --val /tmp/vd_val.txt --out /tmp/vekil_duman \
	--n-train 256 --n-val 64 --epochs 1 --seeds 0 2>&1 | grep -v -i warn
