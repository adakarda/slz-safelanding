#!/bin/bash
# AirSim gosterimi (Arda istedi, 19.10): en iyi model (tarama c13 tohum 0: 30 s + kayarken alcal + kalkan egitimde)
# 4 havada rastgele baslangictan, ikisi GT ikisi v3 etiketle, gorus pencereleri acik. Olcum degil, gosterim.
# Dosya adi havada_sonra.sh: tarama orkestratoru bu ad calisirken yeni egitim baslatmiyor (AirSim'e oncelik).
{
M=$HOME/rl_inis/kos/arama/t2_c13_f_kayarak_kalkan/model.zip
WS=$HOME/ros2_ws
S=$WS/src/eland_airsim/scripts
while pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null || pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do sleep 30; done
echo "[gosterim] $(date +%H:%M) basliyor; model $M"
for kosu in "rastgele:101 gt" "rastgele:102 gt" "rastgele:103 v3" "rastgele:104 v3"; do
	set -- $kosu
	L=$HOME/eland_veri/_gunlukler/gosterim_$(date +%H%M%S)_$2
	V3=""; [ "$2" = v3 ] && V3=--v3
	echo "[gosterim] $(date +%H:%M) $1 ($2)"
	bash $S/run_airsim.sh --havada $1 --rl $M --kalkan 10 --trigger --izle $V3 --log-dir $L > $L.out 2>&1 &
	R=$!
	for _ in $(seq 1 420); do
		grep -qE "hazir\. Kapatmak|HATA" $L.out 2>/dev/null && break
		kill -0 $R 2>/dev/null || break
		sleep 1
	done
	grep -E "rastgele havada|havada:|secildi|HATA" $L.out | sed 's/^/   /'
	if grep -q "hazir\. Kapatmak" $L.out; then
		PYTHONPATH="$WS/src/eland_airsim:${PYTHONPATH:-}" $HOME/airsim-venv/bin/python -m eland_airsim.inis_sina \
			--out $L/inis.json > $L/inis_sina.log 2>&1
		python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('   sonuc', d.get('sonuc'), '| sure', d.get('sure_s'), 's | sinif', d.get('inis_sinifi'), '| temas', d.get('carpisma_nesnesi'))" $L/inis.json 2>/dev/null
		sleep 10                    # a moment to look at the landed vehicle
	fi
	kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
	for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || tasklist.exe 2>/dev/null | grep -qi AirSimNH || break; sleep 1; done
	sleep 5
done
echo "[gosterim] $(date +%H:%M) bitti"
exit
}
