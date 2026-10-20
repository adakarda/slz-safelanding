#!/bin/bash
source $HOME/rl_inis/ortam.sh
date +%H:%M; free -m | awk 'NR==2 {print "mevcut MB:", $7}'
AV=$(free -m | awk 'NR==2 {print $7}'); [ "$AV" -lt 2500 ] && { echo "bellek az, cikiyorum"; exit 1; }
pgrep -af '[e]land_rl\.(train|evaluate)' | grep -oE '\-\-(out|model) [^ ]+'
D=$HOME/eland_veri/rl/messi_ds4
cd /tmp && $RL_PY -c "import sys; sys.argv=['x','$D/test.txt','$HOME/rl_inis/kos/messi_a1_s0/model.zip']; exec(open('$HOME/rl_inis/tanilama/tampon_politika.py').read())" 2>&1 | grep -v -i warn
