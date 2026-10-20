#!/bin/bash
# Duzeltme 4: sora_v1 + entropi (ana) ve paper + entropi (kontrol), paralel; her biri sonra degerlendirilir.
source $HOME/rl_inis/ortam.sh
S=$HOME/rl_inis/sahneler_pilot.txt
kos() {   # ad odul
	O=$HOME/rl_inis/kos/$1; mkdir -p $O
	cd $HOME/rl_inis
	$RL_PY -u -m eland_rl.train --scenes $S --steps 1000000 --seed 0 --reward $2 --ent-coef 0.01 --out $O >$O/egitim.log 2>&1
	echo "[$1] egitim cikis $?: $(tail -n 1 $O/egitim.log)"
	for odul in sora_v1 paper; do
		$RL_PY -u -m eland_rl.evaluate --scenes $S --model $O/model.zip --starts 15 --reward $odul --out $O/eval_$odul.csv >$O/eval_$odul.txt 2>&1
	done
	echo "[$1] degerlendirme bitti"
}
kos sora_v1_s0 sora_v1 &
kos paper_ent_s0 paper &
wait
echo "[v1] hepsi bitti"
