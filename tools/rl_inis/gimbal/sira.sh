#!/bin/bash
# Duzeltme 25c (AirSim, RL + gimbal) ve 25a (ortamda gimbal degerlendirmesi). hiz2 zincirinin Duzeltme 23 olcumu
# bitince (hiz2/h23_sonuc.txt) ve egitimlerden once kosar; bitince (ya da hata verirse) gimbal/hazir dosyasini yazar,
# yanal hiz ve gimbal egitimleri (hiz2_tur.py) onu bekler.
#   bash ~/rl_inis/gimbal/sira.sh
{
source $HOME/rl_inis/ortam.sh
S=$HOME/ros2_ws/src/eland_airsim/scripts; G=$HOME/eland_veri/_gunlukler; P=$HOME/rl_inis/airsim_pilot
Y=$HOME/rl_inis/gimbal; K=$HOME/rl_inis/kos; D=$HOME/eland_veri/rl/messi_ds4
CSV=$HOME/eland_veri/airsim_nh_havada_t2026.csv
M=$K/arama/t3_c23_b1_adim05_alcal1_s1/model.zip
rm -f $Y/hazir
trap 'touch $Y/hazir' EXIT
while [ ! -s $HOME/rl_inis/hiz2/h23_sonuc.txt ]; do sleep 30; done
while pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do sleep 30; done
echo "[gimbal] $(date +%H:%M) 25c: AirSim, RL + gimbal, 30 havada baslangic"
ad=f9_rl_k10_gt_gimbal
bash $S/inis_sina.sh $CSV --etiket $ad --rl $M --kalkan 10 --gimbal \
	| grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
KOK=$(ls -td $G/airsim_inis_${ad}_*/ | head -1)
cp ${KOK}sonuc.jsonl $G/airsim_faz3/${ad}.jsonl
(cd /tmp && ~/v3_test/venv/bin/python $P/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}.jsonl) | tail -1
python3 $Y/h25c_karar.py | tee $Y/h25c_sonuc.txt
echo "[gimbal] $(date +%H:%M) 25a: ortamda gimbal degerlendirmesi, 7 model"
O=$K/gimbal_deger; mkdir -p $O
while read -r dizin tur; do
	ad=$(basename $dizin)
	[ -s $O/$ad.csv ] && continue
	if [ "$tur" = C13 ]; then B=(--reward zemin_v3 --diag --shield-train-m 10); else B=(--reward zemin_v1); fi
	$RL_PY -m eland_rl.evaluate --scenes $D/val_b32.txt --starts 10 --obs sem_depth_sora --sora-cell 0.25 --only-rl --kalkan2 \
		--env-json '{"gimbal": true}' --model $dizin/model.zip "${B[@]}" --out $O/$ad.csv > $O/$ad.txt 2>&1 \
		|| echo "[gimbal] $ad: HATA ($(tail -1 $O/$ad.txt))"
done <<LISTE
$K/arama/t2_c13_f_kayarak_kalkan C13
$K/arama/t3_c13_f_kayarak_kalkan_s1 C13
$K/arama/t3_c13_f_kayarak_kalkan_s2 C13
$K/arama/t2_c23_b1_adim05_alcal1 C23
$K/arama/t3_c23_b1_adim05_alcal1_s1 C23
$K/arama/t3_c23_b1_adim05_alcal1_s2 C23
$K/b_B2_s0 C23
LISTE
python3 $Y/h25a_karar.py | tee $Y/h25a_sonuc.txt
echo "[gimbal] $(date +%H:%M) bitti"
exit
}
