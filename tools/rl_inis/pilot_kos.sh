#!/bin/bash
# Pilot (Duzeltme 2): 5 foto, 500k adim, tohum 0; sonra sabit baslangicli degerlendirme.
source $HOME/rl_inis/ortam.sh
O=$HOME/rl_inis/kos/pilot_s0
mkdir -p $O
cd $HOME/rl_inis
$RL_PY -u -m eland_rl.train --scenes $HOME/rl_inis/sahneler_pilot.txt --steps 500000 --seed 0 --out $O >$O/egitim.log 2>&1
echo "egitim cikis kodu $?"
tail -1 $O/egitim.log
$RL_PY -u -m eland_rl.evaluate --scenes $HOME/rl_inis/sahneler_pilot.txt --model $O/model.zip --starts 15 --out $O/eval.csv 2>&1 | tee $O/eval.txt
