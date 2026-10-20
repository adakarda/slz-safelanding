#!/bin/bash
# Duzeltme 9, B deneyi: 3 kol x 3 tohum, 1M adim; egitim train_b, degerlendirme val_b32 (10 baslangic).
# Ayni anda en fazla 2 egitim (Depth Anything kollari dahil); yeni kosu icin en az 7 GB bos bellek.
# On planda calisir: wsl.exe istemcisi bagli kalir. Yarim kalan kosu son checkpoint'ten surer.
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos
touch $K/B_CALISIYOR; trap 'rm -f $K/B_CALISIYOR' EXIT
[ -f $D/val_b32.txt ] || awk 'NR % 3 == 1' $D/val_b.txt > $D/val_b32.txt
cd $HOME/rl_inis

kos() {  # ad tohum odul [ek]
	local AD=$1 S=$2 R=$3 EK=$4
	local O=$K/b_${AD}_s${S}
	mkdir -p $O
	if [ ! -f $O/model.zip ]; then
		local C DEVAM=
		C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
		[ -n "$C" ] && DEVAM="--resume $C"
		echo "[b] $AD s$S basladi $(date +%H:%M) ${DEVAM:-sifirdan}"
		$RL_PY -u -m eland_rl.train --scenes $D/train_b.txt --shard --sora-cell 0.25 --steps 1000000 --seed $S \
			--reward $R --ent-coef 0.01 --obs sem_depth_sora --vec dummy $EK $DEVAM --out $O >> $O/egitim.log 2>&1
		echo "[b] $AD s$S egitim bitti $(date +%H:%M): $(tail -n 1 $O/egitim.log)"
	fi
	if [ ! -f $O/eval_val.csv ]; then
		$RL_PY -u -m eland_rl.evaluate --scenes $D/val_b32.txt --sora-cell 0.25 --model $O/model.zip --starts 10 \
			--reward $R --obs sem_depth_sora --oracle --out $O/eval_val.csv > $O/eval_val.txt 2>&1
	fi
	echo "[b] $AD s$S degerlendirme bitti $(date +%H:%M)"
	grep -E '^(rl|rl_kalkan|duz_inis|duz_kalkan) ' -A0 $O/eval_val.txt | cut -c1-60 | sed "s/^/[b] $AD s$S /"
}

yer_bekle() {
	while [ "$(pgrep -fc '[e]land_rl\.train')" -ge 2 ] || [ "$(free -m | awk 'NR==2 {print $7}')" -lt 7000 ]; do
		sleep 60
	done
}

echo "[b] kuyruk basladi $(date +%H:%M)"
for S in 0 1 2; do
	for KOL in "B0:sora_v1:" "B1:zemin_v1:" "B2:zemin_v1:--mirror"; do
		IFS=: read -r AD R EK <<< "$KOL"
		yer_bekle
		kos "$AD" "$S" "$R" "$EK" &
		sleep 180     # egitim belleğini alsin, sonra yeniden olc
	done
done
wait
echo "[b] butun kosular bitti $(date +%H:%M)"
