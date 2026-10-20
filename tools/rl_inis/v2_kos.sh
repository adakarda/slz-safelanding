#!/bin/bash
# Duzeltme 5: sora_v1 + entropi + SORA kanali, tohum 0 ve 1 paralel; sonra degerlendirme.
source $HOME/rl_inis/ortam.sh
S=$HOME/rl_inis/sahneler_pilot.txt
kos() {   # ad tohum
	O=$HOME/rl_inis/kos/$1; mkdir -p $O
	cd $HOME/rl_inis
	$RL_PY -u -m eland_rl.train --scenes $S --steps 1000000 --seed $2 --reward sora_v1 --ent-coef 0.01 \
		--obs sem_depth_sora --out $O >$O/egitim.log 2>&1
	echo "[$1] egitim cikis $?: $(tail -n 1 $O/egitim.log)"
	$RL_PY -u -m eland_rl.evaluate --scenes $S --model $O/model.zip --starts 15 --reward sora_v1 \
		--obs sem_depth_sora --out $O/eval_sora_v1.csv >$O/eval_sora_v1.txt 2>&1
	echo "[$1] degerlendirme: $(grep '^rl ' $O/eval_sora_v1.txt | cut -c1-80)"
}
kos sora_v2_s0 0 &
kos sora_v2_s1 1 &
wait
echo "[v2] hepsi bitti"
