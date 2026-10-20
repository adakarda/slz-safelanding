#!/bin/bash
# 2026-10-17 13:55 yurutme notu: A1'i 600k checkpoint'inden surdur, DA kollarini bastan baslat, A2b kuyrugu
set -e
K=$HOME/rl_inis/kos
if pgrep -f '[e]land_rl\.train' >/dev/null; then echo "egitim zaten kosuyor, cikiyorum"; exit 1; fi
mkdir -p $K/_olu
[ -d $K/da_P0 ] && mv $K/da_P0 $K/_olu/da_P0_0125
[ -f $K/messi_a1_s0/egitim_0-753k.log ] || mv $K/messi_a1_s0/egitim.log $K/messi_a1_s0/egitim_0-753k.log
cd $HOME/rl_inis
AD=messi_a1_s0 EK="--resume $K/messi_a1_s0/ckpt/model_600000_steps.zip" setsid nohup bash messi/a1_kos.sh > $K/a1_devam.out 2>&1 < /dev/null &
sleep 2
setsid nohup bash messi/a2b_kuyruk.sh > $K/a2b_kuyruk.out 2>&1 < /dev/null &
setsid nohup bash derinlik/da_kollar.sh > $K/da_kollar.out 2>&1 < /dev/null &
sleep 5
pgrep -af '[e]land_rl\.train|[_]kos\.sh|[d]a_kollar|[k]uyruk'
