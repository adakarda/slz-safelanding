#!/bin/bash
# Duzeltme 7 on sinyali (egitimsiz): kanal pilotu test ucusunda, uc SORA kanaliyla.
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4
O=$HOME/rl_inis/kos/da_sinyal; mkdir -p $O
cd $HOME/rl_inis
for K in "gt:--sem-source gt" "v3:--sem-source pred" "v3_da:--sem-source pred --sora-elev-tau 0.12"; do
	AD=${K%%:*}; ARG=${K#*:}
	$RL_PY -u -m eland_rl.evaluate --scenes $D/test_foto.txt --sora-cell 0.25 --starts 15 --reward sora_v1 \
		--obs sem_depth_sora $ARG --out $O/$AD.csv > $O/$AD.txt 2>&1
	echo "== $AD"; grep -E '^(duz_inis|kanal) ' $O/$AD.txt | cut -c1-150
done
