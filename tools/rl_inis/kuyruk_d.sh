#!/bin/bash
# Duzeltme 12, D deneyi: D1 = egitimde 30 s sinir x 3 tohum, 1M adim; odul C deneyinin kararina gore.
# C kuyrugu ve AirSim Faz 6 bitince baslar. Ayni anda en fazla 2 egitim; yeni kosu icin en az 7 GB bos bellek.
# On planda calisir: wsl.exe istemcisi bagli kalir. Yarim kalan kosu son checkpoint'ten surer.
{
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos
cd $HOME/rl_inis

while [ -f $K/C_CALISIYOR ] || pgrep -f '[f]az6_zemin_v2\.sh|[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do
	sleep 60
done
touch $K/D_CALISIYOR; trap 'rm -f $K/D_CALISIYOR' EXIT
if python3 h11_karar.py | grep -q '^KARAR: zemin_v2 benimsenir'; then R=zemin_v2; else R=zemin_v1; fi
echo "[d] kuyruk basladi $(date +%H:%M); odul $R (C deneyinin karari)"

kos() {  # tohum
	local S=$1
	local O=$K/d_D1_s${S}
	mkdir -p $O
	if [ ! -f $O/model.zip ]; then
		local C DEVAM=
		C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
		[ -n "$C" ] && DEVAM="--resume $C"
		echo "[d] D1 s$S basladi $(date +%H:%M) ${DEVAM:-sifirdan}"
		$RL_PY -u -m eland_rl.train --scenes $D/train_b.txt --shard --sora-cell 0.25 --steps 1000000 --seed $S \
			--reward $R --max-t 30 --ent-coef 0.01 --obs sem_depth_sora --vec dummy $DEVAM --out $O >> $O/egitim.log 2>&1
		echo "[d] D1 s$S egitim bitti $(date +%H:%M): $(tail -n 1 $O/egitim.log)"
	fi
	if [ ! -f $O/eval_val.csv ]; then
		$RL_PY -u -m eland_rl.evaluate --scenes $D/val_b32.txt --sora-cell 0.25 --model $O/model.zip --starts 10 \
			--reward $R --obs sem_depth_sora --oracle --out $O/eval_val.csv > $O/eval_val.txt 2>&1
	fi
	echo "[d] D1 s$S degerlendirme bitti $(date +%H:%M)"
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
echo "[d] butun kosular bitti $(date +%H:%M)"
python3 $HOME/rl_inis/h12_karar.py
exit
}
