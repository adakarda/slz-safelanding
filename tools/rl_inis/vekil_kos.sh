#!/bin/bash
# Duzeltme 10, asama 1: vekil gorev. Bellek uygun olunca (>= 4.5 GB bos, en cok 1 egitim) kosar.
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos; O=$K/vekil
mkdir -p $O; touch $K/VEKIL_CALISIYOR; trap 'rm -f $K/VEKIL_CALISIYOR' EXIT
awk 'NR % 4 == 1' $D/train_b.txt > $O/train_b150.txt
echo "[vekil] bekliyor $(date +%H:%M)"
while [ "$(pgrep -fc '[e]land_rl\.train')" -ge 2 ] || [ "$(free -m | awk 'NR==2 {print $7}')" -lt 4500 ]; do sleep 60; done
echo "[vekil] basladi $(date +%H:%M)"
cd $HOME/rl_inis && $RL_PY -u -m eland_rl.vekil --train $O/train_b150.txt --val $D/val_b32.txt --out $O 2>&1 | grep -v -i warn
echo "[vekil] bitti $(date +%H:%M)"
