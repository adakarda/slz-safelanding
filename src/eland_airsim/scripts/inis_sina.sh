#!/bin/bash
# Faz 3: birden cok baslangictan acil inis, AirSim gercegiyle olculur (eland_airsim.inis_sina).
#
#   src/eland_airsim/scripts/inis_sina.sh BASLANGIC_CSV [--v3] [--etiket AD] [--irtifa 25]
#
# BASLANGIC_CSV: x_ned,y_ned[,...] satirlari (baslik satiri atlanir; orto_analiz.py'nin baslangiclar.csv'si).
# Her satir icin run_airsim.sh --takeoff --trigger --no-hud --baslangic X,Y [--v3] acilir, inis olculur,
# kosu kapatilir. Sonuclar ~/eland_veri/_gunlukler/airsim_inis_<etiket>_<zaman>/sonuc.jsonl.
set -u
WS=$(cd "$(dirname "$0")/../../.." && pwd)
CSV=$1; shift
V3=""; ETIKET=gt; IRTIFA=25
while [ $# -gt 0 ]; do
	case "$1" in
	--v3) V3=--v3; ETIKET=v3 ;;
	--etiket) ETIKET=$2; shift ;;
	--irtifa) IRTIFA=$2; shift ;;
	*) echo "bilinmeyen secenek: $1"; exit 2 ;;
	esac
	shift
done
KOK=$HOME/eland_veri/_gunlukler/airsim_inis_${ETIKET}_$(date +%Y%m%d_%H%M%S)
mkdir -p "$KOK"
cp "$CSV" "$KOK/baslangiclar.csv"
i=0
# read the list first: tasklist.exe and friends inside the loop would otherwise eat the loop's stdin
mapfile -t SATIRLAR < <(tail -n +2 "$CSV" | tr -d '\r')
for satir in "${SATIRLAR[@]}"; do
	IFS=, read -r X Y _ <<<"$satir"
	i=$((i + 1))
	# WSL memory gate: RL trainings share the 12 GB; the pipeline needs ~1.5 GB, v3 ~2 GB more (_tahmin)
	GEREK=$([ -n "$V3" ] && echo 5000 || echo 3000)
	while [ "$(free -m | awk 'NR==2 {print $7}')" -lt "$GEREK" ]; do
		echo "[inis] $(date +%H:%M) WSL bos bellek $(free -m | awk 'NR==2 {print $7}') MB < $GEREK, bekleniyor"; sleep 60
	done
	D=$KOK/k$(printf %02d $i)
	echo "[inis] $(date +%H:%M) kosu $i: baslangic ($X, $Y) $V3"
	bash "$WS/src/eland_airsim/scripts/run_airsim.sh" --takeoff "$IRTIFA" --trigger --no-hud \
		--baslangic "$X,$Y" $V3 --log-dir "$D" >"$D.out" 2>&1 &
	R=$!
	for _ in $(seq 1 400); do
		grep -qE "hazir\. Kapatmak|HATA" "$D.out" 2>/dev/null && break
		kill -0 $R 2>/dev/null || break
		sleep 1
	done
	if grep -q "hazir\. Kapatmak" "$D.out"; then
		grep "irtifa" "$D.out" | sed 's/^/   /'
		PYTHONPATH="$WS/src/eland_airsim:${PYTHONPATH:-}" "$HOME/airsim-venv/bin/python" -m eland_airsim.inis_sina \
			--out "$D/inis.json" 2>&1 | grep '^\[inis\]' | sed 's/^/   /'
		[ -f "$D/inis.json" ] || echo '{"sonuc": "olcum_hatasi"}' >"$D/inis.json"
	else
		echo "   kosu baslamadi:"; tail -3 "$D.out" | sed 's/^/   /'
		echo '{"sonuc": "baslamadi"}' >"$D/inis.json" 2>/dev/null || { mkdir -p "$D"; echo '{"sonuc": "baslamadi"}' >"$D/inis.json"; }
	fi
	# what the detector decided, for the report
	grep -E "eligible=|aday yok" "$D/pipeline.log" 2>/dev/null | tail -2 | cut -c1-220 >"$D/dedektor_son.txt"
	python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d.update(kosu=int(sys.argv[2]), x=float(sys.argv[3]), y=float(sys.argv[4]), kol=sys.argv[5]); print(json.dumps(d, ensure_ascii=False))" \
		"$D/inis.json" "$i" "$X" "$Y" "$ETIKET" >>"$KOK/sonuc.jsonl"
	kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
	for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || tasklist.exe 2>/dev/null | grep -qi AirSimNH || break; sleep 1; done
	sleep 3
done
echo "[inis] $(date +%H:%M) bitti: $KOK/sonuc.jsonl"
python3 - "$KOK/sonuc.jsonl" <<'PY'
import json, sys
rs = [json.loads(l) for l in open(sys.argv[1])]
indi = [r for r in rs if r.get('sonuc') == 'indi']
guv = [r for r in indi if r.get('inis_sinifi') in (0, 1)]
print(f'{len(rs)} kosu, {len(indi)} indi, {len(guv)} guvenli sinifa ({sorted(set(r["sonuc"] for r in rs))})')
if indi:
    print('temas hizi m/s:', [r['temas_hizi_mps'] for r in indi])
    print('inis sinifi:', [r['inis_sinifi'] for r in indi], ' carpisma:', [r['carpisma_nesnesi'] for r in indi])
PY
