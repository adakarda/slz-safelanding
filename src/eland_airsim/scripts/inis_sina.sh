#!/bin/bash
# Faz 3/4: birden cok baslangictan inis, AirSim gercegiyle olculur (eland_airsim.inis_sina).
#
#   src/eland_airsim/scripts/inis_sina.sh BASLANGIC_CSV [--v3] [--rl MODEL.zip] [--kalkan M] [--etiket AD]
#                                         [--irtifa 25] [--ruzgar KUZEY,DOGU,ASAGI]
#
# BASLANGIC_CSV: x_ned,y_ned[,...] satirlari (baslik satiri atlanir; orto_analiz.py'nin baslangiclar.csv'si).
# Basligi x_ned,y_ned,hedef_n,hedef_e,irtifa olan liste (scripts/havada_sec.py --n) havada baslangictir:
# her satira run_airsim.sh --havada N,E,IRTIFA eklenir (kalkis 30 m, sonra hedefe ucus, tetik orada).
# Her satir icin run_airsim.sh --takeoff --trigger --no-hud --baslangic X,Y [--v3] [--rl ...] acilir, inis
# olculur, kosu kapatilir. Sonuclar ~/eland_veri/_gunlukler/airsim_inis_<etiket>_<zaman>/sonuc.jsonl.
# Her kosudan once ve sonra yetim ROS dugumu aranir (ilk Faz 3 kosusunda birikmislerdi).
{
set -u
WS=$(cd "$(dirname "$0")/../../.." && pwd)
CSV=$1; shift
V3=""; ETIKET=""; IRTIFA=25; RL=(); RL_AD=""
while [ $# -gt 0 ]; do
	case "$1" in
	--v3) V3=--v3 ;;
	--rl) RL+=(--rl "$2"); RL_AD=rl_$(basename "$(dirname "$2")"); shift ;;
	--kalkan) RL+=(--kalkan "$2"); RL_AD="${RL_AD}_k$2"; shift ;;
	--hizli-son) RL+=(--hizli-son "$2"); RL_AD="${RL_AD}_hs$2"; shift ;;
	--gimbal) RL+=(--gimbal); RL_AD="${RL_AD}_gimbal" ;;
	--etiket) ETIKET=$2; shift ;;
	--irtifa) IRTIFA=$2; shift ;;
	--ruzgar) RL+=(--ruzgar "$2"); RL_AD="${RL_AD:-klasik}_r$(echo "$2" | tr -d ' ' | tr ',' '_')"; shift ;;
	*) echo "bilinmeyen secenek: $1"; exit 2 ;;
	esac
	shift
done
[ -n "$ETIKET" ] || ETIKET=${RL_AD:-klasik}_$([ -n "$V3" ] && echo v3 || echo gt)
KOK=$HOME/eland_veri/_gunlukler/airsim_inis_${ETIKET}_$(date +%Y%m%d_%H%M%S)
mkdir -p "$KOK"
cp "$CSV" "$KOK/baslangiclar.csv"
DUGUMLER="hud_node detector_node mapping_node perception_node tracker_node rl_landing_mode"
yetim_var() { for ad in $DUGUMLER; do pgrep -x "$ad" >/dev/null && return 0; done; pgrep emergency_land >/dev/null; }
i=0
# read the list first: tasklist.exe and friends inside the loop would otherwise eat the loop's stdin
mapfile -t SATIRLAR < <(tail -n +2 "$CSV" | tr -d '\r')
BASLIK=$(head -n 1 "$CSV" | tr -d '\r')
for satir in "${SATIRLAR[@]}"; do
	IFS=, read -r X Y C3 C4 C5 _ <<<"$satir,,,,"
	HAV=(); KALKIS=$IRTIFA; HAV_AD=""
	if [[ "$BASLIK" == *hedef_n* ]]; then      # air start: climb to 30 m, fly over, trigger there
		HAV=(--havada "$C3,$C4,$C5"); KALKIS=30; HAV_AD="$C3,$C4,$C5"
	fi
	i=$((i + 1))
	if yetim_var; then
		echo "[inis] UYARI: onceki kosudan kalan dugum var, kapatiliyor"
		for ad in $DUGUMLER; do pkill -x "$ad" 2>/dev/null; done; pkill emergency_land 2>/dev/null; sleep 2
	fi
	# WSL memory gate: RL trainings share the 12 GB; the pipeline needs ~1.5 GB, v3 ~2 GB more (_tahmin)
	GEREK=$([ -n "$V3" ] && echo 5000 || echo 3000)
	while [ "$(free -m | awk 'NR==2 {print $7}')" -lt "$GEREK" ]; do
		echo "[inis] $(date +%H:%M) WSL bos bellek $(free -m | awk 'NR==2 {print $7}') MB < $GEREK, bekleniyor"; sleep 60
	done
	# AirSim died in the middle of several Faz 3 runs (all RPC connections reset at once, PX4 froze in
	# lockstep, the mode aborted on "no request from FMU"). Such an attempt is repeated, up to 3 in all,
	# and counted: "deneme" is how many it took, "coken" how many died.
	coken=0
	for deneme in 1 2 3; do
		# Windows memory gate too (run_airsim.sh refuses below 2.5 GB; one Faz 3 start was lost to it)
		while true; do
			WB=$(powershell.exe -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -dc 0-9)
			[ -z "$WB" ] || [ "$WB" -ge 2000 ] && break
			echo "[inis] $(date +%H:%M) Windows bos bellek $WB MB < 2000, bekleniyor"; sleep 60
		done
		# a PX4 left by an earlier attempt blocks every later start (Faz 7, 2026-10-21). Only AirSim's own PX4
		# (working directory rootfs_airsim) is closed; a Gazebo session is never touched.
		for p in $(pgrep -x px4); do
			case "$(readlink /proc/$p/cwd 2>/dev/null)" in
			*rootfs_airsim*) echo "[inis] UYARI: onceki denemeden kalan AirSim PX4'u ($p) kapatiliyor"
				kill $p 2>/dev/null; sleep 3; kill -9 $p 2>/dev/null; sleep 5 ;;
			esac
		done
		D=$KOK/k$(printf %02d $i)$([ "$deneme" -gt 1 ] && echo "_$deneme")
		echo "[inis] $(date +%H:%M) kosu $i (deneme $deneme): baslangic ($X, $Y)${HAV_AD:+ havada ($HAV_AD)} $V3 ${RL[*]}"
		bash "$WS/src/eland_airsim/scripts/run_airsim.sh" --takeoff "$KALKIS" --trigger --no-hud \
			--baslangic "$X,$Y" "${HAV[@]}" $V3 "${RL[@]}" --log-dir "$D" >"$D.out" 2>&1 &
		R=$!
		for _ in $(seq 1 400); do
			grep -qE "hazir\. Kapatmak|HATA" "$D.out" 2>/dev/null && break
			kill -0 $R 2>/dev/null || break
			sleep 1
		done
		if grep -q "hazir\. Kapatmak" "$D.out"; then
			grep -E "irtifa|secildi|havada:" "$D.out" | sed 's/^/   /'
			PYTHONPATH="$WS/src/eland_airsim:${PYTHONPATH:-}" "$HOME/airsim-venv/bin/python" -m eland_airsim.inis_sina \
				--out "$D/inis.json" >"$D/inis_sina.log" 2>&1
			grep '^\[inis\]' "$D/inis_sina.log" | sed 's/^/   /'
			[ -f "$D/inis.json" ] || { echo '{"sonuc": "olcum_hatasi"}' >"$D/inis.json"; tail -3 "$D/inis_sina.log" | sed 's/^/   /'; }
		else
			echo "   kosu baslamadi:"; tail -3 "$D.out" | sed 's/^/   /'
			mkdir -p "$D"; echo '{"sonuc": "baslamadi"}' >"$D/inis.json"
		fi
		# for the report: what the detector decided; when the bridge first lost AirSim; whether the mode aborted
		grep -E "eligible=|aday yok" "$D/pipeline.log" 2>/dev/null | tail -2 | cut -c1-220 >"$D/dedektor_son.txt"
		KOPMA=$(grep -m1 -oE "^\[WARN\] \[[0-9]{10}" "$D/kopru.log" 2>/dev/null | grep -oE "[0-9]{10}")
		MOD_DUSTU=$(grep -c "no request received from FMU" "$D/pipeline.log" 2>/dev/null)
		kill -TERM $R 2>/dev/null; wait $R 2>/dev/null
		for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || tasklist.exe 2>/dev/null | grep -qi AirSimNH || break; sleep 1; done
		sleep 3
		SONUC=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print('olcum_kacti' if d.get('sonuc') == 'zaman_asimi' and d.get('px4_yerde') else d.get('sonuc'))" "$D/inis.json")
		# a landing PX4 saw but the measurement missed is a measurement failure, not a mode failure
		[ "$SONUC" = olcum_kacti ] && { echo "   [inis] PX4 yerde ama olcum inisi kacirdi; yeniden"; continue; }
		if [ -n "$KOPMA" ] || [ "${MOD_DUSTU:-0}" -gt 0 ] || [[ "$SONUC" =~ ^(olcum_hatasi|airsim_yok|kopma|baslamadi)$ ]]; then
			coken=$((coken + 1))
			echo "   [inis] AirSim/olcum koptu (kopru ilk uyari $([ -n "$KOPMA" ] && date -d @$KOPMA +%H:%M:%S || echo -), mod dustu $MOD_DUSTU); yeniden"
			[ "$SONUC" = indi ] && [ -z "$KOPMA" ] && break     # landed and measured before the drop: keep it
			continue
		fi
		break
	done
	python3 -c "import json,sys; d=json.load(open(sys.argv[1])); d.update(kosu=int(sys.argv[2]), x=float(sys.argv[3]), y=float(sys.argv[4]), kol=sys.argv[5], deneme=int(sys.argv[6]), coken=int(sys.argv[7])); sys.argv[8] and d.update(havada=[float(v) for v in sys.argv[8].split(',')]); print(json.dumps(d, ensure_ascii=False))" \
		"$D/inis.json" "$i" "$X" "$Y" "$ETIKET" "$deneme" "$coken" "$HAV_AD" >>"$KOK/sonuc.jsonl"
	yetim_var && echo "[inis] UYARI: kosu $i kapandiktan sonra dugum kaldi"
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
exit
}
