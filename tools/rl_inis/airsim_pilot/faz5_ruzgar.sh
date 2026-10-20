#!/bin/bash
# Faz 5: sabit 5 m/s dogu ruzgari, klasik (W1) ve RL B2-s0 (W2). faz34_ikinci_tur.sh bitince calisir.
S=$HOME/ros2_ws/src/eland_airsim/scripts/inis_sina.sh
CSV=$HOME/eland_veri/airsim_nh_baslangiclar.csv
G=$HOME/eland_veri/_gunlukler
M=/home/arda/rl_inis/kos/b_B2_s0/model.zip
while pgrep -f 'airsim_pilot/faz34_ikinci_tur.sh' >/dev/null; do sleep 60; done
kol() {
	ad=$1; et=$2; shift 2
	echo "[faz5] $(date +%H:%M) $ad basliyor"
	bash $S $CSV --etiket "$et" "$@" | grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
	K=$(ls -td $G/airsim_inis_${et}_*/ | head -1)
	cp ${K}sonuc.jsonl $G/airsim_faz3/${ad}.jsonl
	(cd /tmp && ~/v3_test/venv/bin/python ~/rl_inis/airsim_pilot/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}.jsonl)
}
kol w1_klasik_gt w1_klasik_gt --ruzgar 0,5,0
kol w2_rl_b2_gt w2_rl_b2_gt --rl $M --ruzgar 0,5,0
echo "[faz5] $(date +%H:%M) bitti"
