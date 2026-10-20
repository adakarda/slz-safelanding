#!/bin/bash
# bir modeli MESSI test, test7 ve egitim orneginde degerlendir: bash degerlendir.sh <kos_klasoru>
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4
O=$1
[ -f $D/train_ornek20.txt ] || awk 'NR % 35 == 1' $D/train.txt | head -20 > $D/train_ornek20.txt
cd $HOME/rl_inis
for L in test test7 train_ornek20; do
	$RL_PY -u -m eland_rl.evaluate --scenes $D/$L.txt --sora-cell 0.25 --model $O/model.zip --starts 15 --reward sora_v1 \
		--obs sem_depth_sora --oracle ${EVAL_EK:-} --out $O/eval_$L.csv > $O/eval_$L.txt 2>&1
	echo "== $L"; grep -E '^(rl|rl_kalkan|duz_inis|kanal|gorus_kahini|rastgele) ' $O/eval_$L.txt | cut -c1-120
done
