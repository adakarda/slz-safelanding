#!/bin/bash
# Duzeltme 11, C deneyi: C1 = zemin_v2 x 3 tohum, 1M adim; egitim train_b, degerlendirme val_b32 (10 baslangic).
# Kiyas B1 (zemin_v1, ayni tohumlar), yeniden kosulmaz. Ayarlar B1 ile ayni: ent 0.01, 4 ortam, --shard,
# SORA hucresi 0.25 m, --vec dummy, aynalama yok.
# Ayni anda en fazla 2 egitim; yeni kosu icin en az 7 GB bos bellek; AirSim oturumu (run_airsim.sh / inis_sina.sh)
# acikken baslamaz (sim yaninda agir CPU PX4 mesajlarini dusuruyor).
# On planda calisir: wsl.exe istemcisi bagli kalir. Yarim kalan kosu son checkpoint'ten surer.
{
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; K=$HOME/rl_inis/kos
touch $K/C_CALISIYOR; trap 'rm -f $K/C_CALISIYOR' EXIT
cd $HOME/rl_inis

kos() {  # ad tohum odul
	local AD=$1 S=$2 R=$3
	local O=$K/c_${AD}_s${S}
	mkdir -p $O
	if [ ! -f $O/model.zip ]; then
		local C DEVAM=
		C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
		[ -n "$C" ] && DEVAM="--resume $C"
		echo "[c] $AD s$S basladi $(date +%H:%M) ${DEVAM:-sifirdan}"
		$RL_PY -u -m eland_rl.train --scenes $D/train_b.txt --shard --sora-cell 0.25 --steps 1000000 --seed $S \
			--reward $R --ent-coef 0.01 --obs sem_depth_sora --vec dummy $DEVAM --out $O >> $O/egitim.log 2>&1
		echo "[c] $AD s$S egitim bitti $(date +%H:%M): $(tail -n 1 $O/egitim.log)"
	fi
	if [ ! -f $O/eval_val.csv ]; then
		$RL_PY -u -m eland_rl.evaluate --scenes $D/val_b32.txt --sora-cell 0.25 --model $O/model.zip --starts 10 \
			--reward $R --obs sem_depth_sora --oracle --out $O/eval_val.csv > $O/eval_val.txt 2>&1
	fi
	echo "[c] $AD s$S degerlendirme bitti $(date +%H:%M)"
	grep -E '^(rl|rl_kalkan|duz_inis|duz_kalkan) ' -A0 $O/eval_val.txt | cut -c1-60 | sed "s/^/[c] $AD s$S /"
}

yer_bekle() {
	while [ "$(pgrep -fc '[e]land_rl\.train')" -ge 2 ] || [ "$(free -m | awk 'NR==2 {print $7}')" -lt 7000 ] \
		|| pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' > /dev/null; do
		sleep 60
	done
}

echo "[c] kuyruk basladi $(date +%H:%M)"
for S in 0 1 2; do
	yer_bekle
	kos C1 "$S" zemin_v2 &
	sleep 180     # egitim bellegini alsin, sonra yeniden olc
done
wait
echo "[c] butun kosular bitti $(date +%H:%M)"
python3 $HOME/rl_inis/h11_karar.py
exit
}
