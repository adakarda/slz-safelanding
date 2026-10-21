#!/bin/bash
# Duzeltme 23 ve 24, sirayla: Faz 7 ve kilitli kalkan olcumu (kos2.sh) bitince
#   1. eland_rl_mode derlenir (hizli_son parametresi; Faz 7 kosarken derlenemezdi, RL kolu o programi kullaniyor)
#   2. kapali dogrulama: yeni program, bayraksiz, tek havada baslangic (dokunus 0.7 m/s, "faster down" satiri yok)
#   3. Duzeltme 23: Faz 7'nin 30 baslangici, ayni model, AirSim etiketi, kalkan 10, --hizli-son 2; karar H23
#   4. Duzeltme 24: yanal hiz turu (hiz2_tur.py); karar H24
#   bash ~/rl_inis/hiz2/zincir.sh
{
source $HOME/rl_inis/ortam.sh
S=$HOME/ros2_ws/src/eland_airsim/scripts; G=$HOME/eland_veri/_gunlukler; P=$HOME/rl_inis/airsim_pilot
CSV=$HOME/eland_veri/airsim_nh_havada_t2026.csv
sleep 120
while pgrep -f '[f]az7_havada\.sh|[r]un_airsim\.sh|[i]nis_sina\.sh|[k]os2\.sh' >/dev/null \
	|| pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null; do
	sleep 60
done
echo "[hiz2] $(date +%H:%M) eland_rl_mode derleniyor"
cd $HOME/ros2_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select eland_rl_mode 2>&1 | tail -2
source install/setup.bash
read -r M MAD <<<"$(python3 $P/faz7_model.py)"
echo "[hiz2] model: $MAD"
kol() {
	ad=$1; liste=$2; shift 2
	echo "[hiz2] $(date +%H:%M) $ad basliyor"
	bash $S/inis_sina.sh $liste --etiket "$ad" "$@" | grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
	K=$(ls -td $G/airsim_inis_${ad}_*/ | head -1)
	cp ${K}sonuc.jsonl $G/airsim_faz3/${ad}.jsonl
	(cd /tmp && ~/v3_test/venv/bin/python $P/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}.jsonl) | tail -1
}
head -2 $CSV > $G/f8_kapali_liste.csv
kol f8_kapali_dogrulama $G/f8_kapali_liste.csv --rl "$M" --kalkan 10
K=$(ls -td $G/airsim_inis_f8_kapali_dogrulama_*/ | head -1)
echo "[hiz2] kapali dogrulama: 'faster down' satiri $(grep -c 'faster down' ${K}k01/rl_mod.log 2>/dev/null), $(grep -m1 'touching down' ${K}k01/rl_mod.log 2>/dev/null | grep -o 'touching down.*')"
kol f8_rl_k10_gt_hs2 $CSV --rl "$M" --kalkan 10 --hizli-son 2
K=$(ls -td $G/airsim_inis_f8_rl_k10_gt_hs2_*/ | head -1)
echo "[hiz2] acik: 'faster down' satiri olan kosu $(grep -l 'faster down' ${K}k*/rl_mod.log 2>/dev/null | wc -l)"
python3 $HOME/rl_inis/hiz2/h23_karar.py | tee $HOME/rl_inis/hiz2/h23_sonuc.txt
echo "[hiz2] $(date +%H:%M) yanal hiz turu"
$RL_PY -u $HOME/rl_inis/hiz2/hiz2_tur.py
echo "[hiz2] $(date +%H:%M) zincir bitti"
exit
}
