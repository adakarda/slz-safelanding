#!/bin/bash
# PD'yi yeniden kos (22:35'te bellek tasmasin diye durduruldu). Ayni ayarlar; en cok 1 egitim kosarken ve
# en az 5.5 GB bos bellek varken baslar. Yarim kalirsa son checkpoint'ten surer.
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos; O=$K/da_PD
ARG="--sem-source pred --depth-mode elev --sora-elev-tau 0.12"
touch $K/DA_CALISIYOR; trap 'rm -f $K/DA_CALISIYOR' EXIT
echo "[pd] bekliyor $(date +%H:%M)"
while [ "$(pgrep -fc '[e]land_rl\.train')" -ge 2 ] || [ "$(free -m | awk 'NR==2 {print $7}')" -lt 5500 ]; do sleep 60; done
cd $HOME/rl_inis
if [ ! -f $O/model.zip ]; then
	C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1); DEVAM=; LOG=$O/egitim_tekrar.log
	[ -n "$C" ] && DEVAM="--resume $C"
	echo "[da] PD yeniden basladi $(date +%H:%M): $ARG ${DEVAM:-sifirdan}" | tee -a $K/akis_b.out
	$RL_PY -u -m eland_rl.train --scenes $D/train_foto.txt --shard --sora-cell 0.25 --steps 1000000 --seed 0 \
		--reward sora_v1 --ent-coef 0.01 --obs sem_depth_sora --vec dummy $ARG --out $O $DEVAM > $LOG 2>&1
	echo "[da] PD egitim bitti $(date +%H:%M): $(tail -n 1 $LOG)" | tee -a $K/akis_b.out
fi
$RL_PY -u -m eland_rl.evaluate --scenes $D/test_foto.txt --sora-cell 0.25 --model $O/model.zip --starts 15 \
	--reward sora_v1 --obs sem_depth_sora $ARG --oracle --out $O/eval_test_foto.csv > $O/eval_test_foto.txt 2>&1
grep -E '^(rl|rl_kalkan|duz_inis|duz_kalkan|kanal|gorus_kahini) ' $O/eval_test_foto.txt | cut -c1-110 | sed "s/^/[da] PD /" | tee -a $K/akis_b.out
