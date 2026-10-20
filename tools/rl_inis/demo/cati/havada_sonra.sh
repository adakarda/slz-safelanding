#!/bin/bash
# AirSim cati gosterimi (Arda istedi, 19.10 23:30: "binalarin catilarinin ustunde test etmek istiyorum").
# En iyi model (tarama c13 tohum 0), kalkan 10 m, AirSim gercek etiketi; HUD + --izle pencereleri acik.
# Her baslangic: bilinen temiz dogma noktasindan kalkis 30 m, bir catinin en ic noktasinin ustune ucus (cati_sec.py),
# orada RL Landing tetiklenir. Olcum degil, gosterim (6 cati, tek kosu).
# Dosya adi havada_sonra.sh: tarama orkestratoru bu ad calisirken yeni egitim baslatmiyor (AirSim'e oncelik).
#
#   bash ~/rl_inis/demo/cati/havada_sonra.sh [LISTE.csv]
{
M=$HOME/rl_inis/kos/arama/t2_c13_f_kayarak_kalkan/model.zip
WS=$HOME/ros2_ws
S=$WS/src/eland_airsim/scripts
LISTE=${1:-$HOME/rl_inis/demo/cati.csv}
OZET=$HOME/rl_inis/demo/cati/sonuc.txt
win_bos() { powershell.exe -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -dc 0-9; }
mapfile -t SATIRLAR < <(tail -n +2 "$LISTE" | tr -d '\r')
echo "[cati] $(date +%H:%M) ${#SATIRLAR[@]} cati; model $M" | tee -a $OZET
k=0
for satir in "${SATIRLAR[@]}"; do
	k=$((k + 1))
	IFS=, read -r X Y HN HE ALT ALAN YARI UYGUN <<<"$satir"
	for _ in $(seq 1 60); do      # trainings stopped for the demo: wait for their memory to come back
		pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null && { sleep 10; continue; }
		[ "$(win_bos)" -ge 1800 ] && break
		sleep 10
	done
	L=$HOME/eland_veri/_gunlukler/cati_$(date +%H%M%S)_$k
	echo "[cati] $(date +%H:%M) $k: dogma ($X, $Y), cati ($HN, $HE) m otede, $ALT m | cati $ALAN m2, ic yaricap $YARI m," \
		"en yakin uygun hucre $UYGUN m; Windows bos $(win_bos) MB" | tee -a $OZET
	bash $S/run_airsim.sh --baslangic "$X,$Y" --havada "$HN,$HE,$ALT" --rl $M --kalkan 10 --trigger --izle \
		--log-dir $L > $L.out 2>&1 &
	R=$!
	for _ in $(seq 1 480); do
		grep -qE "hazir\. Kapatmak|HATA" $L.out 2>/dev/null && break
		kill -0 $R 2>/dev/null || break
		sleep 1
	done
	grep -E "havada:|secildi|HATA|BEKCI" $L.out | sed 's/^/   /' | tee -a $OZET
	if grep -q "hazir\. Kapatmak" $L.out; then
		PYTHONPATH="$WS/src/eland_airsim:${PYTHONPATH:-}" $HOME/airsim-venv/bin/python -m eland_airsim.inis_sina \
			--out $L/inis.json > $L/inis_sina.log 2>&1
		python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('   sonuc', d.get('sonuc'), '| sure', d.get('sure_s'), 's | sinif', d.get('inis_sinifi'), '| alt siniflar', d.get('alt_siniflar'), '| temas', d.get('carpisma_nesnesi'))" $L/inis.json 2>&1 | tee -a $OZET
		sleep 15                    # a moment to look at the landed vehicle
	fi
	kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
	for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || tasklist.exe 2>/dev/null | grep -qi AirSimNH || break; sleep 1; done
	sleep 5
done
echo "[cati] $(date +%H:%M) bitti" | tee -a $OZET
exit
}
