#!/bin/bash
# Duzeltme 22: kilitli kalkanin degerlendirmesi. Var olan modeller, val_b32 x 10, yalniz yeni yontem (rl_kalkan2); rl ve rl_kalkan eski CSV'lerde (degerlendirme deterministik, bit bit ayni oldugu gosterildi).
# Tek tek kosar; her degerlendirmeden once WSL'de en az 3 GB bos bellek bekler (yanda bir egitim kosuyor).
# Faz 7 (AirSim) bitene kadar bekler.
#   bash ~/rl_inis/yedek/kos2.sh
{
source $HOME/rl_inis/ortam.sh
K=$HOME/rl_inis/kos; Y=$K/kalkan2; D=$HOME/eland_veri/rl/messi_ds4
mkdir -p $Y
while pgrep -f '[f]az7_havada\.sh|[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do sleep 60; done
ORTAK="--scenes $D/val_b32.txt --starts 10 --obs sem_depth_sora --sora-cell 0.25 --only-rl --yalniz-kalkan2"
C13="--reward zemin_v3 --diag --shield-train-m 10"
C23="--reward zemin_v1"
while read -r dizin bayrak; do
	ad=$(basename $dizin)
	[ -s $Y/$ad.csv ] && { echo "[kalkan2] $ad: var, atlandi"; continue; }
	while [ "$(free -m | awk 'NR==2 {print $7}')" -lt 3000 ]; do sleep 30; done
	echo "[kalkan2] $(date +%H:%M) $ad"
	$RL_PY -m eland_rl.evaluate $ORTAK --model $dizin/model.zip ${!bayrak} --out $Y/$ad.csv > $Y/$ad.txt 2>&1 \
		|| echo "[kalkan2] $ad: HATA ($(tail -1 $Y/$ad.txt))"
done <<LISTE
$K/arama/t2_c13_f_kayarak_kalkan C13
$K/arama/t3_c13_f_kayarak_kalkan_s1 C13
$K/arama/t3_c13_f_kayarak_kalkan_s2 C13
$K/arama/t2_c23_b1_adim05_alcal1 C23
$K/arama/t3_c23_b1_adim05_alcal1_s1 C23
$K/arama/t3_c23_b1_adim05_alcal1_s2 C23
$K/b_B2_s0 C23
LISTE
python3 $HOME/rl_inis/yedek/h22_karar.py | tee $Y/karar.txt
echo "[kalkan2] $(date +%H:%M) bitti"
exit
}
