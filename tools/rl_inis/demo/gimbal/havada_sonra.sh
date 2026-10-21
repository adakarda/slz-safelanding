#!/bin/bash
# AirSim gimbal gosterimi (Arda istedi, 21.10: "segmentasyon kamerasi calisan gimball airsim simulasyonundan acar misin
# bir kesit gozumle goreyim"). Faz 7 bitince 3 RL inisi: c23 s1 (Faz 7 modeli), AirSim etiketi, kalkan 10, --gimbal,
# --izle pencereleri. Yaninda kamera_izle.py aracin ve kameranin egimini kaydeder (gimbal calisiyor mu).
# Olcum degil, gosterim. Dosya adi havada_sonra.sh: tarama tipi orkestratorler bu ad calisirken egitim baslatmaz.
{
S=$HOME/ros2_ws/src/eland_airsim/scripts
G=$HOME/eland_veri/_gunlukler
M=$HOME/rl_inis/kos/arama/t3_c23_b1_adim05_alcal1_s1/model.zip
sleep 60
while pgrep -f '[f]az7_havada\.sh|[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do sleep 30; done
echo "[gimbal] $(date +%H:%M) basliyor; model $M"
for kosu in "rastgele:201" "rastgele:202" "rastgele:203"; do
	L=$G/gimbal_$(date +%H%M%S)
	echo "[gimbal] $(date +%H:%M) $kosu"
	bash $S/run_airsim.sh --havada $kosu --rl $M --kalkan 10 --trigger --izle --gimbal --log-dir $L > $L.out 2>&1 &
	R=$!
	for _ in $(seq 1 420); do
		grep -qE "AirSim API hazir|HATA" $L.out 2>/dev/null && break
		sleep 1
	done
	$HOME/airsim-venv/bin/python $HOME/rl_inis/demo/gimbal/kamera_izle.py 400 > $L.egim.txt 2>&1 &
	IZ=$!
	for _ in $(seq 1 420); do
		grep -qE "hazir\. Kapatmak|HATA" $L.out 2>/dev/null && break
		kill -0 $R 2>/dev/null || break
		sleep 1
	done
	grep -E "havada:|secildi|HATA" $L.out | sed 's/^/   /'
	if grep -q "hazir\. Kapatmak" $L.out; then
		PYTHONPATH="$HOME/ros2_ws/src/eland_airsim:${PYTHONPATH:-}" $HOME/airsim-venv/bin/python -m eland_airsim.inis_sina \
			--out $L/inis.json > $L/inis_sina.log 2>&1
		python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('   sonuc', d.get('sonuc'), '| sure', d.get('sure_s'), 's | sinif', d.get('inis_sinifi'), '| temas', d.get('carpisma_nesnesi'), '| temas hizi', d.get('temas_hizi_mps'))" $L/inis.json 2>&1
		sleep 15
	fi
	kill $IZ 2>/dev/null
	python3 - $L.egim.txt <<'PY'
import re, statistics as st, sys
v, k = [], []
for l in open(sys.argv[1]):
    m = re.search(r'arac pitch\s+(-?[\d.]+) roll\s+(-?[\d.]+) \| kamera pitch\s+(-?[\d.]+) roll\s+(-?[\d.]+)', l)
    if m:
        a = [float(x) for x in m.groups()]
        v.append(max(abs(a[0]), abs(a[1])))
        k.append((a[2], a[3]))
if v:
    print(f'   egim: arac en cok {max(v):.1f} derece; kamera pitch {min(p for p, _ in k):.1f}..{max(p for p, _ in k):.1f}, '
          f'roll {min(r for _, r in k):.1f}..{max(r for _, r in k):.1f} ({len(v)} olcum)')
PY
	kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
	for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || tasklist.exe 2>/dev/null | grep -qi AirSimNH || break; sleep 1; done
	sleep 5
done
echo "[gimbal] $(date +%H:%M) bitti"
exit
}
