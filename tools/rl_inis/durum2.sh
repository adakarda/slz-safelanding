#!/bin/bash
free -m | awk 'NR==2 {print "bellek MB kullanilan:", $3, "/", $2} NR==3 {print "swap MB:", $3}'
nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader
for D in messi_a1_s0/devam600000 da_P0; do P=$HOME/rl_inis/kos/$D/progress.csv; [ -f $P ] && echo "$D: $(wc -l < $P) satir" ; done
tail -n 3 $HOME/rl_inis/kos/messi_a1_s0/egitim.log; tail -n 3 $HOME/rl_inis/kos/da_P0/egitim.log
