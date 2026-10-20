#!/bin/bash
# Duzeltme 14, F deneyi: F1 = zemin_v3 + egitimde 30 s x 3 tohum, 1M adim; kiyas B1 (D1 tanimlayici).
# E kuyrugu uc tohumu da baslatana kadar bekler. Ayni anda en fazla 2 egitim; yeni kosu icin en az 7 GB bos bellek;
# AirSim acikken baslamaz. On planda calisir: wsl.exe istemcisi bagli kalir. Yarim kalan kosu son checkpoint'ten surer.
{
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos
cd $HOME/rl_inis

while [ ! -f $K/e_E1_s2/args.json ] || ! grep -q zemin_v3 $HOME/ros2_ws/src/eland_rl/eland_rl/env.py; do
	sleep 60
done
touch $K/F_CALISIYOR; trap 'rm -f $K/F_CALISIYOR' EXIT
echo "[f] kuyruk basladi $(date +%H:%M); odul zemin_v3, egitimde 30 s"

kos() {  # tohum
	local S=$1
	local O=$K/f_F1_s${S}
	mkdir -p $O
	if [ ! -f $O/model.zip ]; then
		local C DEVAM=
		C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
		[ -n "$C" ] && DEVAM="--resume $C"
		echo "[f] F1 s$S basladi $(date +%H:%M) ${DEVAM:-sifirdan}"
		$RL_PY -u -m eland_rl.train --scenes $D/train_b.txt --shard --sora-cell 0.25 --steps 1000000 --seed $S \
			--reward zemin_v3 --max-t 30 --ent-coef 0.01 --obs sem_depth_sora --vec dummy $DEVAM --out $O >> $O/egitim.log 2>&1
		echo "[f] F1 s$S egitim bitti $(date +%H:%M): $(tail -n 1 $O/egitim.log)"
	fi
	if [ ! -f $O/eval_val.csv ]; then
		$RL_PY -u -m eland_rl.evaluate --scenes $D/val_b32.txt --sora-cell 0.25 --model $O/model.zip --starts 10 \
			--reward zemin_v3 --obs sem_depth_sora --oracle --out $O/eval_val.csv > $O/eval_val.txt 2>&1
	fi
	echo "[f] F1 s$S degerlendirme bitti $(date +%H:%M)"
}

yer_bekle() {
	while [ "$(pgrep -fc '[e]land_rl\.train')" -ge 2 ] || [ "$(free -m | awk 'NR==2 {print $7}')" -lt 7000 ] \
		|| pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' > /dev/null; do
		sleep 60
	done
}

for S in 0 1 2; do
	yer_bekle
	kos "$S" &
	sleep 180
done
wait
echo "[f] butun kosular bitti $(date +%H:%M)"
python3 $HOME/rl_inis/h14_karar.py
exit
}
