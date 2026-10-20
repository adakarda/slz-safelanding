#!/bin/bash
# Havada baslangic denemesi (dal havada, ~/ros2_ws_h): Faz 6 bitince, D egitimi baslamadan once 2 kosu.
# D kuyrugu C_CALISIYOR bayragini bekler; bayrak bu deneme bitene kadar tutulur, her durumda kaldirilir.
{
K=$HOME/rl_inis/kos
H=$HOME/ros2_ws_h/src/eland_airsim/scripts
touch $K/C_CALISIYOR; trap 'rm -f $K/C_CALISIYOR; echo "[havada] D serbest"' EXIT
while pgrep -f '[f]az6_zemin_v2\.sh' >/dev/null; do sleep 20; done
echo "[havada] $(date +%H:%M) Faz 6 bitti; havada baslangic denemesi (B2-s0, GT, kalkan 10)"
python3 $H/havada_sec.py --tohum 11 --n 2 --cikti $HOME/eland_veri/havada_dene.csv
cat $HOME/eland_veri/havada_dene.csv
bash $H/inis_sina.sh $HOME/eland_veri/havada_dene.csv --rl $K/b_B2_s0/model.zip --kalkan 10 --etiket havada_dene \
	| grep -E "kosu [0-9]+ \(|^   |bitti|guvenli sinifa|UYARI|baslamadi"
S=$(ls -td $HOME/eland_veri/_gunlukler/airsim_inis_havada_dene_*/ | head -1)
(cd /tmp && ~/v3_test/venv/bin/python $HOME/rl_inis/airsim_pilot/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz ${S}sonuc.jsonl) | tail -1
echo "[havada] $(date +%H:%M) deneme bitti: ${S}"
exit
}
