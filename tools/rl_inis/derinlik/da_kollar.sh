#!/bin/bash
# Duzeltme 7: Depth Anything deneyinin 5 kolu, sirayla; her biri 1M adim + test ucusu degerlendirmesi.
# Biten kol atlanir; yarim kalan kol son checkpoint'ten surer (yurutme notu 2026-10-17).
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4
cd $HOME/rl_inis
for K in "P0:--sem-source gt" "PA:--sem-source pred" "PB:--sem-source pred --depth-mode elev" \
         "PC:--sem-source pred --sora-elev-tau 0.12" "PD:--sem-source pred --depth-mode elev --sora-elev-tau 0.12"; do
	AD=${K%%:*}; ARG=${K#*:}
	O=$HOME/rl_inis/kos/da_$AD; mkdir -p $O
	[ -f $O/eval_test_foto.csv ] && { echo "[da] $AD zaten bitti"; continue; }
	if [ ! -f $O/model.zip ]; then
		C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
		LOG=$O/egitim.log; DEVAM=
		if [ -n "$C" ]; then DEVAM="--resume $C"; LOG=$O/egitim_devam$(basename $C .zip | tr -dc 0-9).log; fi
		echo "[da] $AD basladi $(date +%H:%M): $ARG ${DEVAM:-sifirdan}"
		$RL_PY -u -m eland_rl.train --scenes $D/train_foto.txt --shard --sora-cell 0.25 --steps 1000000 --seed 0 \
			--reward sora_v1 --ent-coef 0.01 --obs sem_depth_sora --vec dummy $ARG --out $O $DEVAM >$LOG 2>&1
		echo "[da] $AD egitim bitti $(date +%H:%M): $(tail -n 1 $LOG)"
	fi
	$RL_PY -u -m eland_rl.evaluate --scenes $D/test_foto.txt --sora-cell 0.25 --model $O/model.zip --starts 15 \
		--reward sora_v1 --obs sem_depth_sora $ARG --oracle --out $O/eval_test_foto.csv >$O/eval_test_foto.txt 2>&1
	grep -E '^(rl|rl_kalkan|duz_inis|kanal|gorus_kahini) ' $O/eval_test_foto.txt | cut -c1-110 | sed "s/^/[da] $AD /"
done
echo "[da] butun kollar bitti $(date +%H:%M)"
