#!/bin/bash
# Duzeltme 13, E deneyi: E1 = D1 + kayarken alcal eylemleri (--diag) x 3 tohum, 1M adim; kiyas D1.
# D kuyrugu uc tohumu da baslatana ve kod (diag_actions) ana dalda olana kadar bekler. Ayni anda en fazla 2 egitim;
# yeni kosu icin en az 7 GB bos bellek; AirSim acikken baslamaz.
# On planda calisir: wsl.exe istemcisi bagli kalir. Yarim kalan kosu son checkpoint'ten surer.
{
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos
cd $HOME/rl_inis

while [ ! -f $K/d_D1_s2/args.json ] || ! grep -q diag_actions $HOME/ros2_ws/src/eland_rl/eland_rl/env.py; do
	sleep 60
done
R=$(python3 -c "import json; print(json.load(open('$K/d_D1_s0/args.json'))['reward'])")
touch $K/E_CALISIYOR; trap 'rm -f $K/E_CALISIYOR' EXIT
echo "[e] kuyruk basladi $(date +%H:%M); odul $R (D1 ile ayni), egitimde 30 s, kayarken alcal"

kos() {  # tohum
	local S=$1
	local O=$K/e_E1_s${S}
	mkdir -p $O
	if [ ! -f $O/model.zip ]; then
		local C DEVAM=
		C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
		[ -n "$C" ] && DEVAM="--resume $C"
		echo "[e] E1 s$S basladi $(date +%H:%M) ${DEVAM:-sifirdan}"
		$RL_PY -u -m eland_rl.train --scenes $D/train_b.txt --shard --sora-cell 0.25 --steps 1000000 --seed $S \
			--reward $R --max-t 30 --diag --ent-coef 0.01 --obs sem_depth_sora --vec dummy $DEVAM --out $O >> $O/egitim.log 2>&1
		echo "[e] E1 s$S egitim bitti $(date +%H:%M): $(tail -n 1 $O/egitim.log)"
	fi
	if [ ! -f $O/eval_val.csv ]; then
		$RL_PY -u -m eland_rl.evaluate --scenes $D/val_b32.txt --sora-cell 0.25 --model $O/model.zip --starts 10 \
			--reward $R --obs sem_depth_sora --diag --oracle --out $O/eval_val.csv > $O/eval_val.txt 2>&1
	fi
	echo "[e] E1 s$S degerlendirme bitti $(date +%H:%M)"
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
echo "[e] butun kosular bitti $(date +%H:%M)"
while [ -f $K/D_CALISIYOR ]; do sleep 60; done     # D1 is the comparison: its evaluations must be in
python3 $HOME/rl_inis/h13_karar.py
exit
}
