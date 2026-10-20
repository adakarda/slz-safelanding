#!/bin/bash
# Ikinci tur R1'in baslamayan 10. baslangicini, Faz 5 bitince yeniden kos ve birlestir.
G=$HOME/eland_veri/_gunlukler
while pgrep -f 'airsim_pilot/faz5_ruzgar.sh' >/dev/null; do sleep 60; done
printf "x_ned,y_ned\n-84.7,-133.9\n" > $HOME/eland_veri/airsim_nh_baslangic10.csv
bash $HOME/ros2_ws/src/eland_airsim/scripts/inis_sina.sh $HOME/eland_veri/airsim_nh_baslangic10.csv --etiket t2_rl_b2_gt_eksik \
	--rl /home/arda/rl_inis/kos/b_B2_s0/model.zip | grep -E "^   \[inis\]|bitti|guvenli"
K=$(ls -td $G/airsim_inis_t2_rl_b2_gt_eksik_*/ | head -1)
cp $G/airsim_faz3/rl_b2_gt_t2.jsonl $G/airsim_faz3/rl_b2_gt_t2_ana.jsonl
python3 $HOME/rl_inis/airsim_pilot/birlestir.py $G/airsim_faz3/rl_b2_gt_t2_ana.jsonl ${K}sonuc.jsonl $G/airsim_faz3/rl_b2_gt_t2.jsonl
(cd /tmp && ~/v3_test/venv/bin/python ~/rl_inis/airsim_pilot/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/rl_b2_gt_t2.jsonl)
echo "[r1eksik] bitti"
