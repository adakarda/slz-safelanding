#!/bin/bash
# AirSim acil inis senaryosu (docs/airsim/SENARYO_PLANI.md, Arda 28.10): her acilista farkli dogma yeri ve ozgun rota
# (30 m, merkez 150 m), rotanin ortasinda acil inis; RL politikasi (c13 s0) + v4 segmentasyonu + gimbal.
#   bash ~/rl_inis/senaryo/senaryo.sh [--kapat] [--tohum N]
#   --kapat: inisten sonra her seyi kapat (toplu kosu icin). Yoksa Ctrl+C'ye kadar acik kalir.
{
D=$HOME/rl_inis/senaryo; S=$HOME/ros2_ws/src/eland_airsim/scripts
M=$HOME/rl_inis/kos/arama/t2_c13_f_kayarak_kalkan/model.zip
KAPAT=0; TOHUM=()
while [ $# -gt 0 ]; do case "$1" in --kapat) KAPAT=1 ;; --tohum) TOHUM=(--tohum "$2"); shift ;; esac; shift; done
if pgrep -f '[e]land_rl\.train|[e]land_rl\.evaluate|[f]aktor\.py' >/dev/null; then
	echo "Bir RL egitimi calisiyor; AirSim'e bellek yetmez."; exit 1; fi
if pgrep -x px4 >/dev/null || pgrep -f '[r]un_airsim\.sh' >/dev/null; then
	echo "Calisan bir benzetim var (px4/run_airsim). Once onu kapat."; exit 1; fi
K=$D/kosular/$(date +%m%d_%H%M%S); mkdir -p $K
ros() { source /opt/ros/jazzy/setup.bash; source $HOME/ros2_ws/install/setup.bash; }
( ros; exec python3 $D/senaryo_ekran.py ) > $K/ekran.log 2>&1 &
EK=$!
for deneme in 1 2; do
	EK_ARG=(); [ $deneme = 2 ] && EK_ARG=(--bilinen)        # 2nd try: a known clear spawn
	python3 $D/senaryo_uret.py --cikti $K/senaryo.json --onizleme $K/onizleme.png "${TOHUM[@]}" "${EK_ARG[@]}" || exit 1
	X=$(python3 -c "import json; print(json.load(open('$K/senaryo.json'))['dogma'][0])")
	Y=$(python3 -c "import json; print(json.load(open('$K/senaryo.json'))['dogma'][1])")
	Z=$(python3 -c "import json; z=json.load(open('$K/senaryo.json')).get('dogma_z'); print('' if z is None else z)")
	bash $S/run_airsim.sh --baslangic "$X,$Y" ${Z:+--dogma-z $Z} --takeoff 30 --rl "$M" --kalkan 10 --gimbal \
		--v3 --seg-model $HOME/v4_seg/best_v4.pth --seg-adi v4 --no-hud --klasiksiz --log-dir $K/calisma_$deneme > $K/run_$deneme.out 2>&1 &
	R=$!
	for _ in $(seq 1 600); do
		grep -qE "hazir\. Kapatmak|HATA" $K/run_$deneme.out 2>/dev/null && break
		kill -0 $R 2>/dev/null || break
		sleep 1
	done
	grep -q "hazir\. Kapatmak" $K/run_$deneme.out && break
	echo "[senaryo] acilis basarisiz ($(grep -m1 HATA $K/run_$deneme.out)); bilinen bir dogma yeriyle yeniden"
	kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
	for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || tasklist.exe 2>/dev/null | grep -qi AirSimNH || break; sleep 1; done
done
if ! grep -q "hazir\. Kapatmak" $K/run_$deneme.out; then echo "[senaryo] acilamadi"; kill $EK; exit 1; fi
echo "[senaryo] $(date +%H:%M:%S) ucus basliyor: $(python3 -c "import json; d=json.load(open('$K/senaryo.json')); print(d['ozet'], 'tohum', d['tohum'])")"
( ros; exec python3 $D/senaryo_ucus.py $K/senaryo.json $K ) 2>&1 | grep --line-buffered -E "rota basladi|ACIL|secildi|SONUC" | sed -u 's/^.*\]: /[senaryo] /'
if [ $KAPAT = 1 ]; then
	kill -TERM $R 2>/dev/null; wait $R 2>/dev/null; kill $EK 2>/dev/null
else
	echo "[senaryo] inis bitti; pencereler acik. Kapatmak icin Ctrl+C."
	wait $R; kill $EK 2>/dev/null
fi
exit
}
