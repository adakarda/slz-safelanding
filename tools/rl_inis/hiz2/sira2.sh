#!/bin/bash
# Gece duzeltmesinden sonraki sira (21.10): gimbal adimi (gimbal/sira.sh: 25c AirSim + 25a degerlendirme) bitince
#   1. Duzeltme 23'un AirSim olcumu yeniden (ilk koşu --hizli-son tamsayi parametresiyle hic baslamadi)
#   2. yanal hiz ve gimbal egitimleri (hiz2_tur.py), temiz ortamda: yalniz ~/rl_inis/ortam.sh (ROS kurulumunun eski
#      eland_rl kopyasi PYTHONPATH'te one gecip eski train.py'yi calistirmisti)
#   bash ~/rl_inis/hiz2/sira2.sh
{
S=$HOME/ros2_ws/src/eland_airsim/scripts; G=$HOME/eland_veri/_gunlukler; P=$HOME/rl_inis/airsim_pilot
CSV=$HOME/eland_veri/airsim_nh_havada_t2026.csv
M=$HOME/rl_inis/kos/arama/t3_c23_b1_adim05_alcal1_s1/model.zip
while [ ! -f $HOME/rl_inis/gimbal/hazir ] || pgrep -f '[g]imbal/sira\.sh' >/dev/null; do sleep 60; done
while pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null || pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null; do sleep 60; done
echo "[sira2] $(date +%H:%M) Duzeltme 23 AirSim olcumu (yeniden)"
ad=f8_rl_k10_gt_hs2
bash $S/inis_sina.sh $CSV --etiket $ad --rl "$M" --kalkan 10 --hizli-son 2 \
	| grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
KOK=$(ls -td $G/airsim_inis_${ad}_*/ | head -1)
echo "[sira2] acik: 'faster down' satiri olan kosu $(grep -l 'faster down' ${KOK}k*/rl_mod.log 2>/dev/null | wc -l)"
cp ${KOK}sonuc.jsonl $G/airsim_faz3/${ad}.jsonl
(cd /tmp && ~/v3_test/venv/bin/python $P/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}.jsonl) | tail -1
python3 $HOME/rl_inis/hiz2/h23_karar.py | tee $HOME/rl_inis/hiz2/h23_sonuc.txt
echo "[sira2] $(date +%H:%M) yanal hiz ve gimbal egitimleri"
env -u PYTHONPATH -u AMENT_PREFIX_PATH bash -c 'source $HOME/rl_inis/ortam.sh; exec $RL_PY -u $HOME/rl_inis/hiz2/hiz2_tur.py'
echo "[sira2] $(date +%H:%M) zincir bitti"
exit
}
