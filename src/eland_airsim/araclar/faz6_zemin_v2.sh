#!/bin/bash
# Faz 6 (docs/onkayit/airsim_faz6_onkayit.md): zemin_v2 (C1) ile B2-s0, AirSimNH, ayni 10 baslangic, kalkan 10 m.
#   A0: B2-s0, v3 etiket | A1: C1, v3 etiket | G1: C1, GT etiket (kiyas: t2_rl_b2_k10_gt, yeniden kosulmaz)
# C kuyrugu bitene ve kullanicinin AirSim oturumu kapanana kadar bekler. C1 tohumu h11_karar.py secer.
# On planda calisir: wsl.exe istemcisi bagli kalir.
{
S=$HOME/ros2_ws/src/eland_airsim/scripts/inis_sina.sh
CSV=$HOME/eland_veri/airsim_nh_baslangiclar.csv
G=$HOME/eland_veri/_gunlukler
P=$HOME/rl_inis/airsim_pilot
B2=$HOME/rl_inis/kos/b_B2_s0/model.zip

while [ -f $HOME/rl_inis/kos/C_CALISIYOR ] || pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null \
	|| pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do
	sleep 60
done
echo "[faz6] $(date +%H:%M) C kuyrugu bitti"

KARAR=$(cd $HOME/rl_inis && python3 h11_karar.py)
echo "$KARAR" | grep -E '^(H11|KARAR|AirSim)' | sed 's/^/[faz6] /'
T=$(echo "$KARAR" | sed -n 's/^AirSim modeli: C1-s\([0-9]\).*/\1/p')
if [ -z "$T" ]; then echo "[faz6] C1 modeli secilemedi; durdu"; exit 1; fi
C1=$HOME/rl_inis/kos/c_C1_s$T/model.zip

# tanimlayici: hafif ortamda ilk yanal eylemin irtifasi (B1 ve C1, 3 tohum), sim acilmadan once
for k in b_B1_s0 b_B1_s1 b_B1_s2 c_C1_s0 c_C1_s1 c_C1_s2; do
	echo "[faz6] ilk yanal (hafif ortam) $k: $(bash $HOME/rl_inis/py.sh eylem_irtifa_env.py $HOME/rl_inis/kos/$k/model.zip zemin_v1 3 2>&1 | grep -E '^bolum')"
done

kol() {
	ad=$1; shift
	echo "[faz6] $(date +%H:%M) $ad basliyor"
	bash $S $CSV --etiket "$ad" --kalkan 10 "$@" | grep -E "kosu [0-9]+ \(|^   \[inis\]|bitti|guvenli sinifa|UYARI|baslamadi"
	K=$(ls -td $G/airsim_inis_${ad}_*/ | head -1)
	cp ${K}sonuc.jsonl $G/airsim_faz3/${ad}.jsonl
	(cd /tmp && ~/v3_test/venv/bin/python $P/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz $G/airsim_faz3/${ad}.jsonl) | tail -1
	echo "[faz6] $ad ilk yanal (AirSim): $(python3 $P/ilk_yanal.py $K | tail -1)"
}
kol f6_a0_b2_k10_v3 --rl $B2 --v3
kol f6_a1_c1s${T}_k10_v3 --rl $C1 --v3
kol f6_g1_c1s${T}_k10_gt --rl $C1
echo "[faz6] $(date +%H:%M) bitti"
cd $G/airsim_faz3 && python3 $P/yumusak_say.py rl_b2_k10_gt_t2.jsonl.harita.jsonl f6_a0_b2_k10_v3.jsonl.harita.jsonl \
	f6_a1_c1s${T}_k10_v3.jsonl.harita.jsonl f6_g1_c1s${T}_k10_gt.jsonl.harita.jsonl
exit
}
