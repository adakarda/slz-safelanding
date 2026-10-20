#!/bin/bash
# Faz 3-4 ikinci tur: PX4 artik kendi rootfs'unda (-w) ve Gazebo esdeger parametreleriyle. Dort kol arka arkaya.
# Her kol bitince sonuc airsim_faz3/<ad>_t2.jsonl'e kopyalanir ve haritayla puanlanir.
S=$HOME/ros2_ws/src/eland_airsim/scripts/inis_sina.sh
CSV=$HOME/eland_veri/airsim_nh_baslangiclar.csv
G=$HOME/eland_veri/_gunlukler
M=/home/arda/rl_inis/kos/b_B2_s0/model.zip
kol() {   # ad, etiket, inis_sina secenekleri...
	ad=$1; et=$2; shift 2
	echo "[tur2] $(date +%H:%M) $ad basliyor"
	bash $S $CSV --etiket "$et" "$@" | grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
	K=$(ls -td $G/airsim_inis_${et}_*/ | head -1)
	cp ${K}sonuc.jsonl $G/airsim_faz3/${ad}_t2.jsonl
	(cd /tmp && ~/v3_test/venv/bin/python ~/rl_inis/airsim_pilot/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}_t2.jsonl)
}
kol klasik_gt t2_klasik_gt
kol rl_b2_gt t2_rl_b2_gt --rl $M
kol rl_b2_k10_gt t2_rl_b2_k10_gt --rl $M --kalkan 10
kol klasik_v3 t2_klasik_v3 --v3
echo "[tur2] $(date +%H:%M) bitti"
