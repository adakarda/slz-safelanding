#!/bin/bash
source $HOME/rl_inis/ortam.sh
free -m | awk 'NR==2 {print "bellek kullanilan/mevcut MB:", $3, $7} NR==3 {print "swap MB:", $3}'
AV=$(free -m | awk 'NR==2 {print $7}')
[ "$AV" -lt 2500 ] && { echo "bellek az ($AV MB), profil yok"; exit 1; }
head -3 $HOME/eland_veri/rl/messi_ds4/train.txt > $HOME/rl_inis/tanilama/rp_liste.txt
cd $HOME/rl_inis/tanilama
$RL_PY -u rollout_profil.py rp_liste.txt > rp.out 2>&1
grep -v -i warn rp.out | grep -E 'torch threads|cumtime|collect_rollouts|step_wait|env.py|camera.py|dynamics.py|scene.py|forward|obs_as_tensor|add\b|buffers.py|monitor.py|dummy_vec|policies.py|distributions|_update_info|callbacks|train\b|isin|cross' | head -40
