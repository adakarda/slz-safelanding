#!/bin/bash
# Faz 7 (docs/onkayit/airsim_faz7_onkayit.md): havada rastgele baslangic, klasik zincir ile RL, GT ve v3 etiket.
# --havada ana dala gecene (havada_sonra.sh denemesi) kadar bekler. 10 baslangic, tohum 2026, kollar sirayla.
{
S=$HOME/ros2_ws/src/eland_airsim/scripts
G=$HOME/eland_veri/_gunlukler
P=$HOME/rl_inis/airsim_pilot
CSV=$HOME/eland_veri/airsim_nh_havada_t2026.csv
while ! grep -q -- '--havada) HAVADA' $S/run_airsim.sh || pgrep -f '[h]avada_sonra\.sh|[e]land_rl\.(train|evaluate)' >/dev/null \
	|| pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do
	sleep 60
done
echo "[faz7] $(date +%H:%M) basliyor"
python3 $S/havada_sec.py --tohum 2026 --n 30 --cikti $CSV && cat $CSV
read -r M MAD <<<"$(python3 $P/faz7_model.py)"
echo "[faz7] RL modeli: $MAD"
kol() {
	ad=$1; shift
	echo "[faz7] $(date +%H:%M) $ad basliyor"
	bash $S/inis_sina.sh $CSV --etiket "$ad" "$@" | grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
	K=$(ls -td $G/airsim_inis_${ad}_*/ | head -1)
	cp ${K}sonuc.jsonl $G/airsim_faz3/${ad}.jsonl
	(cd /tmp && ~/v3_test/venv/bin/python $P/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}.jsonl) | tail -1
}
kol f7_klasik_gt
kol f7_rl_k10_gt --rl "$M" --kalkan 10
kol f7_klasik_v3 --v3
kol f7_rl_k10_v3 --rl "$M" --kalkan 10 --v3
echo "[faz7] $(date +%H:%M) bitti"
cd $G/airsim_faz3 && python3 $P/yumusak_say.py f7_klasik_gt.jsonl.harita.jsonl f7_rl_k10_gt.jsonl.harita.jsonl \
	f7_klasik_v3.jsonl.harita.jsonl f7_rl_k10_v3.jsonl.harita.jsonl
python3 $P/sure_kiyas.py f7_klasik_gt f7_rl_k10_gt f7_klasik_v3 f7_rl_k10_v3
exit
}
