#!/bin/bash
# egitim hiz profili; ciktiyi hiz_olc.out'a yazar
source $HOME/rl_inis/ortam.sh
head -10 $HOME/eland_veri/rl/messi_ds4/train.txt > /tmp/hiz_liste.txt
cd $HOME/rl_inis/tanilama && $RL_PY -u hiz_olc.py /tmp/hiz_liste.txt > hiz_olc.out 2>&1
echo "cikis $?"; grep -v -i 'warn' hiz_olc.out | tail -45
