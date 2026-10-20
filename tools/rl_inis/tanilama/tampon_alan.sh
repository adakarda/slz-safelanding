#!/bin/bash
source $HOME/rl_inis/ortam.sh
date +%H:%M; free -m | awk 'NR==2 {print "mevcut MB:", $7}'
AV=$(free -m | awk 'NR==2 {print $7}'); [ "$AV" -lt 1200 ] && { echo "bellek az, cikiyorum"; exit 1; }
D=$HOME/eland_veri/rl/messi_ds4
cd /tmp && for L in test train_ornek20; do echo "== $L"; $RL_PY -c "import sys; sys.argv=['x','$D/$L.txt']; exec(open('$HOME/rl_inis/tanilama/tampon_alan.py').read())"; done
