#!/bin/bash
# denetim verisi: bash uret.sh [model.zip] [baslangic_sayisi] [cikti.json]
source /opt/ros/jazzy/setup.bash
M=${1:-}
if [ -z "$M" ]; then
	if [ -f $HOME/rl_inis/kos/pilot_s0/model.zip ]; then M=$HOME/rl_inis/kos/pilot_s0/model.zip
	else M=$(ls -t $HOME/rl_inis/kos/pilot_s0/ckpt/*.zip | head -1); fi
fi
echo "model: $M"
bash $HOME/rl_inis/py.sh denetim/veri.py $HOME/rl_inis/sahneler_pilot.txt "$M" ${2:-3} ${3:-$HOME/rl_inis/denetim/denetim.json}
