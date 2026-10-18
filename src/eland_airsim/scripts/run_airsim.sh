#!/bin/bash
# run_sim.sh'in AirSim karsiligi: Windows'ta AirSim, WSL'de PX4 SITL (none_iris) + uXRCE-DDS + kopru + algi zinciri.
#
#   src/eland_airsim/scripts/run_airsim.sh [--dunya AirSimNH] [--takeoff 25] [--trigger] [--no-hud]
#                                           [--station] [--px4-param K=V]... [--log-dir DIR] [--zorla]
#                                           [--yalniz-px4]   (yalniz AirSim + PX4; ROS 2 tarafi acilmaz)
#                                           [--params FILE] [--v3] [--baslangic X,Y[,YAW_DERECE]]
#   --v3         maskeyi AirSim'in gercek etiketi yerine v3 uretir (~/v3_test/v3_airsim.py); algi zinciri
#                calisma basina kopyalanan parametre dosyasiyla /eland/v3/etiket'i okur, kod degismez
#   --baslangic  aracin dogdugu nokta, PlayerStart'a gore NED metre (kuzey, dogu) ve yon
#   [--rl MODEL.zip] [--kalkan METRE] [--ruzgar KUZEY,DOGU,ASAGI] [--izle]
#   --station ile: klavyeyle uc (1 arm, 2 kalkis, 3 manuel, W/A/S/D Q/E R/F), 0 acil inis (--rl ise RL Landing)
#   --rl         klasik mod yerine RL: eland_rl_mode + eland_rl.policy_node (konum /eland/gercek_poz'dan,
#                etiket AirSim'den ya da --v3 ile v3'ten); --trigger RL modunu secer. --kalkan: SORA kalkani
#   --ruzgar     sabit ruzgar, m/s NED (AirSim simSetWind; kopru basinda uygulanir)
#   --izle       AirSim penceresinde asagi kameranin goruntu + segmentasyon alt pencereleri; ayrica
#                v3 paneli (--v3) ve politikanin gordugu (--rl) icin goruntu pencereleri
#   --havada N,E,IRTIFA | rastgele[:TOHUM]
#                havada baslangic: kalkistan sonra dogma noktasina gore (N, E) m'ye ve IRTIFA m'ye ucar, orada
#                bekler; tetik (--trigger ya da istasyonda 0) orada verilir. rastgele: dogma noktasi bilinen
#                guvenli noktalardan, hedef 10-50 m otede, 20-30 m (scripts/havada_sec.py). Kalkis 30 m.
#
# Gazebo'ya dokunmaz: eland_sim.launch.py aynen kullanilir (Gazebo kopruleri bosta bekler), PX4 ayri bir
# rootfs'te calisir (rootfs_airsim) ki Gazebo kosularinin kayitli parametreleri karismasin.
# PX4 parametreleri: Gazebo rootfs'unun kayitli degerleri (config/px4_gazebo_esdeger.params) + istenenler.
#
# The whole body is one { ... } block: bash parses it completely before running it, so editing this file
# while a run is going cannot make that run read half-old, half-new lines when it resumes after `wait`.
{
set -u
WS_DIR=$(cd "$(dirname "$0")/../../.." && pwd)
PX4_DIR=$HOME/PX4-Autopilot
PX4_BIN=$PX4_DIR/build/px4_sitl_default/bin
AIRSIM_DIR=/mnt/c/Users/arda_/airsim
VENV=$HOME/airsim-venv
DUNYA=AirSimNH; TAKEOFF_ALT=""; DO_TRIGGER=0; HUD=true; HUD_VIEW=true; STATION=false; PX4_PARAMS=""; ZORLA=0
YALNIZ_PX4=0; PARAMS=""; V3=0; BASLANGIC=""; RL_MODEL=""; KALKAN=-1; RUZGAR=""; IZLE=0; HAVADA=""
LOG_DIR=$HOME/eland_veri/_gunlukler/airsim_$(date +%Y%m%d_%H%M%S)
while [ $# -gt 0 ]; do
	case "$1" in
	--dunya) DUNYA=$2; shift ;;
	--takeoff) TAKEOFF_ALT=$2; shift ;;
	--trigger) DO_TRIGGER=1 ;;
	--no-hud) HUD=false; HUD_VIEW=false ;;
	--station) STATION=true; HUD_VIEW=false ;;
	--px4-param) PX4_PARAMS="$PX4_PARAMS $2"; shift ;;
	--log-dir) LOG_DIR=$2; shift ;;
	--zorla) ZORLA=1 ;;
	--yalniz-px4) YALNIZ_PX4=1 ;;
	--params) PARAMS=$2; shift ;;
	--v3) V3=1 ;;
	--baslangic) BASLANGIC=$2; shift ;;
	--rl) RL_MODEL=$2; shift ;;
	--kalkan) KALKAN=$2; shift ;;
	--ruzgar) RUZGAR=$2; shift ;;
	--izle) IZLE=1 ;;
	--havada) HAVADA=$2; shift ;;
	-h | --help) sed -n 2,27p "$0"; exit 0 ;;
	*) echo "bilinmeyen secenek: $1"; exit 2 ;;
	esac
	shift
done
fail() { echo "[run_airsim] HATA: $*"; exit 1; }
if [[ "$HAVADA" == rastgele* ]]; then      # spawn on known clear ground, target drawn around it
	SECIM=$(python3 "$WS_DIR/src/eland_airsim/scripts/havada_sec.py" \
		$([[ "$HAVADA" == rastgele:* ]] && echo "--tohum ${HAVADA#rastgele:}") \
		$([ -n "$BASLANGIC" ] && echo "--baslangic $BASLANGIC")) || fail "havada_sec.py: hedef secilemedi"
	[ -n "$BASLANGIC" ] || BASLANGIC=${SECIM% *}
	HAVADA=${SECIM#* }
	echo "[run_airsim] rastgele havada baslangic: dogma ($BASLANGIC), hedef (K, D, irtifa) = ($HAVADA)"
fi
if [ -n "$HAVADA" ]; then
	[[ "$HAVADA" =~ ^-?[0-9.]+,-?[0-9.]+,[0-9.]+$ ]] || fail "--havada N,E,IRTIFA ya da rastgele[:TOHUM] olmali: $HAVADA"
	[ -n "$TAKEOFF_ALT" ] || TAKEOFF_ALT=30     # climb above the trees before flying over to the target
fi
EXE="$AIRSIM_DIR/$DUNYA/$DUNYA/WindowsNoEditor/$DUNYA.exe"
[ -f "$EXE" ] || fail "AirSim dunyasi yok: $EXE"
[ -x "$PX4_BIN/px4" ] || fail "PX4 derlenmemis: $PX4_BIN/px4"
command -v MicroXRCEAgent >/dev/null || fail "MicroXRCEAgent PATH'te yok"
[ -x "$VENV/bin/python" ] || fail "AirSim istemci ortami yok: $VENV"

# ------------------------------------------------------------ on kontroller
if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null || pgrep -x gz >/dev/null; then
	fail "calisan bir sim var (px4/gz); once onu kapat"
fi
tasklist.exe 2>/dev/null | grep -qi "$DUNYA.exe" && fail "AirSim zaten acik ($DUNYA.exe); once kapat"
BOS_MB=$(powershell.exe -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -dc 0-9)
echo "[run_airsim] Windows bos bellek: ${BOS_MB:-?} MB"
if [ -n "$BOS_MB" ] && [ "$BOS_MB" -lt 1800 ] && [ "$ZORLA" = 0 ]; then
	fail "Windows bos bellegi 1.8 GB alti; egitimler bitince dene ya da --zorla"
fi
GW=$(ip route | awk '$1 == "default" {print $3; exit}')
[ -n "$GW" ] || fail "Windows adresi (varsayilan ag gecidi) bulunamadi"
mkdir -p "$LOG_DIR"
echo "[run_airsim] gunlukler: $LOG_DIR; Windows: $GW"

AIRSIM_PID=""; PX4_PID=""; AGENT_PID=""; KOPRU_PID=""; LAUNCH_PID=""; BEKCI_PID=""; V3_PID=""; RLM_PID=""; POL_PID=""; RLT_PID=""
temizle() {
	echo "[run_airsim] kapatiliyor..."
	[ -n "$BEKCI_PID" ] && kill "$BEKCI_PID" 2>/dev/null
	for p in $RLT_PID $POL_PID $RLM_PID $LAUNCH_PID $KOPRU_PID $AGENT_PID $V3_PID; do kill -INT "$p" 2>/dev/null; done
	sleep 2
	# the model node can take a few seconds to release CUDA
	for _ in 1 2 3 4 5; do [ -n "$V3_PID" ] && kill -0 "$V3_PID" 2>/dev/null || break; sleep 1; done
	[ -n "$PX4_PID" ] && kill "$PX4_PID" 2>/dev/null
	for p in $POL_PID $RLM_PID $LAUNCH_PID $KOPRU_PID $AGENT_PID $PX4_PID $V3_PID; do kill -9 "$p" 2>/dev/null; done
	# By name too, as run_sim.sh does: ros2 launch's children outlive a killed launcher. In the first
	# Faz 3 batch they piled up run after run (~1.2 GB each; WSL free memory fell to 623 MB) and the
	# old detectors kept publishing candidates into the next run.
	for ad in hud_node detector_node mapping_node perception_node image_bridge tracker_node obstacle_driver \
		rl_landing_mode control_station rqt_image_view p_kestirici; do
		pkill -x "$ad" 2>/dev/null
	done
	pkill emergency_land 2>/dev/null   # emergency_landing_mode, comm truncated to 15 characters
	pkill -f 'eland_airsim\.rl_tetik' 2>/dev/null   # python3 -m: its comm is python3
	pkill -x MicroXRCEAgent 2>/dev/null
	taskkill.exe /IM "$DUNYA.exe" /F >/dev/null 2>&1
	echo "[run_airsim] kapandi"
}
trap temizle EXIT
trap 'exit 130' INT TERM      # exit, so EXIT runs temizle once and nothing after `wait` runs

# ------------------------------------------------------------ AirSim
AYAR_WIN='C:\Users\arda_\airsim\settings_px4.json'
python3 - "$WS_DIR/src/eland_airsim/config/settings_px4.json" "$AIRSIM_DIR/settings_px4.json" "$GW" "$BASLANGIC" "$IZLE" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
v = s['Vehicles']['PX4']
v['LocalHostIp'] = sys.argv[3]
if sys.argv[4]:
    b = [float(x) for x in sys.argv[4].split(',')]
    v['X'], v['Y'] = b[0], b[1]
    if len(b) > 2:
        v['Yaw'] = b[2]
if sys.argv[5] == '1':   # --izle: the downward camera's image and segmentation in AirSim's own window
    s['SubWindows'] = [{'WindowID': i, 'CameraName': 'asagi', 'ImageType': t, 'VehicleName': 'PX4', 'Visible': True}
                       for i, t in ((0, 0), (1, 5))]
json.dump(s, open(sys.argv[2], 'w'), indent=2)
PY
cp "$AIRSIM_DIR/settings_px4.json" "$LOG_DIR/settings_px4.json"
echo "[run_airsim] AirSim aciliyor ($DUNYA)..."
"$EXE" -settings="$AYAR_WIN" -windowed -ResX=1280 -ResY=720 >"$LOG_DIR/airsim.log" 2>&1 &
AIRSIM_PID=$!
# bekci: Windows'ta bos bellek 30 s boyunca 500 MB altinda kalirsa AirSim kapatilir (egitimler WSL'de surer)
(
	dusuk=0
	while sleep 5; do
		b=$(powershell.exe -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -dc 0-9)
		[ -z "$b" ] && continue
		if [ "$b" -lt 500 ]; then dusuk=$((dusuk + 5)); else dusuk=0; fi
		if [ $dusuk -ge 30 ]; then
			echo "[run_airsim] BEKCI: Windows bos bellek $b MB, AirSim kapatiliyor"
			taskkill.exe /IM "$DUNYA.exe" /F >/dev/null 2>&1
			break
		fi
	done
) &
BEKCI_PID=$!
for _ in $(seq 1 120); do
	python3 -c "import socket,sys; socket.create_connection(('$GW', 41451), 1)" 2>/dev/null && break
	sleep 1
done
python3 -c "import socket; socket.create_connection(('$GW', 41451), 1)" 2>/dev/null ||
	fail "AirSim API'si ($GW:41451) acilmadi. Guvenlik duvari izni istendiyse 'Izin ver' de."
echo "[run_airsim]   AirSim API hazir"

# ------------------------------------------------------------ PX4 (ayri rootfs)
R=$PX4_DIR/build/px4_sitl_default/rootfs_airsim
mkdir -p "$R"
[ -e "$R/etc" ] || ln -s ../rootfs/etc "$R/etc"
echo "[run_airsim] PX4 SITL (none_iris) baslatiliyor..."
(
	cd "$R" || exit 1
	# -w is required: without it PX4 v1.17 ignores the current directory and runs in build/rootfs, which is
	# Gazebo's -- the first AirSim runs (18.10 00:03-03:00) overwrote its saved parameters that way
	# (SYS_AUTOSTART 10016); restored from the last Gazebo flight log with tanilama/param_geri_yukle.py.
	PX4_SYS_AUTOSTART=10016 PX4_SIM_MODEL=none_iris PX4_SIM_HOSTNAME="$GW" exec ../bin/px4 -d -w "$R"
) >"$LOG_DIR/px4.log" 2>&1 &
PX4_PID=$!
for _ in $(seq 1 90); do
	grep -q "Simulator connected on TCP port" "$LOG_DIR/px4.log" 2>/dev/null && break
	sleep 1
done
grep -q "Simulator connected on TCP port" "$LOG_DIR/px4.log" || fail "PX4 AirSim'e baglanamadi, bak: $LOG_DIR/px4.log"
for _ in $(seq 1 60); do
	grep -q "Startup script returned successfully" "$LOG_DIR/px4.log" 2>/dev/null && break
	sleep 1
done
echo "[run_airsim]   PX4 AirSim'e bagli"
# the PX4 parameters the Gazebo rootfs carries (config/px4_gazebo_esdeger.params), then the caller's
while read -r ad deger _; do
	case "$ad" in "" | \#*) continue ;; esac
	timeout 10 "$PX4_BIN/px4-param" set "$ad" "$deger" >/dev/null 2>&1
done <"$WS_DIR/src/eland_airsim/config/px4_gazebo_esdeger.params"
echo "[run_airsim]   PX4: Gazebo esdeger parametreleri uygulandi (MPC_Z_VEL_MAX_DN 2.0 ...)"
for kv in $PX4_PARAMS; do
	timeout 10 "$PX4_BIN/px4-param" set "${kv%%=*}" "${kv#*=}" >/dev/null 2>&1 && echo "[run_airsim]   PX4 param $kv"
done
if [ "$YALNIZ_PX4" = 1 ]; then
	echo "[run_airsim] hazir (yalniz AirSim + PX4). Kapatmak icin Ctrl+C."
	wait "$PX4_PID"
	exit 0
fi

# ------------------------------------------------------------ ROS 2
MicroXRCEAgent udp4 -p 8888 >"$LOG_DIR/agent.log" 2>&1 &
AGENT_PID=$!
set +u
source /opt/ros/jazzy/setup.bash
source "$WS_DIR/install/setup.bash"
set -u
RUZGAR_ARG=()
if [ -n "$RUZGAR" ]; then      # a ROS double array: "5,0,0" -> [5.00,0.00,0.00]
	RUZGAR_ARG=(-p "ruzgar_ned:=[$(echo "$RUZGAR" | awk -F, '{printf "%.2f,%.2f,%.2f", $1, $2, $3}')]")
	echo "[run_airsim]   ruzgar ${RUZGAR_ARG[1]#ruzgar_ned:=} m/s (NED)"
fi
"$VENV/bin/python" -m eland_airsim.kopru --ros-args -p host:="$GW" "${RUZGAR_ARG[@]}" >"$LOG_DIR/kopru.log" 2>&1 &
KOPRU_PID=$!
[ -n "$PARAMS" ] || PARAMS=$(ros2 pkg prefix eland_sim)/share/eland_sim/config/eland_params.yaml
if [ "$V3" = 1 ]; then
	# per-run copy: only perception_node's segmentation_topic changes, the original file is untouched
	python3 - "$PARAMS" "$LOG_DIR/params_v3.yaml" <<'PY'
import sys, yaml
p = yaml.safe_load(open(sys.argv[1]))
p['perception_node']['ros__parameters']['segmentation_topic'] = '/eland/v3/etiket'
yaml.safe_dump(p, open(sys.argv[2], 'w'), sort_keys=False)
PY
	PARAMS=$LOG_DIR/params_v3.yaml
	"$HOME/v3_test/venv/bin/python" -P "$HOME/v3_test/v3_airsim.py" >"$LOG_DIR/v3.log" 2>&1 &
	V3_PID=$!
	echo "[run_airsim]   v3 dugumu baslatildi (algi zinciri /eland/v3/etiket'i okuyacak)"
	[ "$IZLE" = 1 ] && ros2 run rqt_image_view rqt_image_view /eland/v3/panel >"$LOG_DIR/izle_v3.log" 2>&1 &
fi
cp "$PARAMS" "$LOG_DIR/params.yaml" 2>/dev/null
# obstacles:=false -- obstacle_driver moves Gazebo models; AirSim has none of them.
# With --rl the Emergency Landing mode stays unregistered (mode:=false): one external mode at a time.
KLASIK_MOD=$([ -n "$RL_MODEL" ] && echo false || echo true)
ros2 launch eland_sim eland_sim.launch.py hud:="$HUD" hud_view:="$HUD_VIEW" station:="$STATION" \
	bridge_colored:=false obstacles:=false mode:="$KLASIK_MOD" params_file:="$PARAMS" >"$LOG_DIR/pipeline.log" 2>&1 &
LAUNCH_PID=$!
if [ -n "$RL_MODEL" ]; then
	[ -f "$RL_MODEL" ] || fail "RL modeli yok: $RL_MODEL"
	ETIKET_KONU=$([ "$V3" = 1 ] && echo /eland/v3/etiket || echo /camera/segmentation)
	KALKAN_F=$(awk -v k="$KALKAN" 'BEGIN{printf "%.2f", k}')    # a ROS double, never "-1"
	(
		set +u
		source "$HOME/rl_inis/ortam.sh"
		exec "$RL_PY" -u -m eland_rl.policy_node --ros-args -p model_path:="$RL_MODEL" \
			-p label_source:=topic -p label_topic:="$ETIKET_KONU" -p pose_source:=topic \
			-p ground_z_m:=0.0 -p kalkan_m:="$KALKAN_F" -p log_csv:="$LOG_DIR/politika.csv"
	) >"$LOG_DIR/politika.log" 2>&1 &
	POL_PID=$!
	for _ in $(seq 1 90); do
		grep -q "policy " "$LOG_DIR/politika.log" 2>/dev/null && break
		kill -0 "$POL_PID" 2>/dev/null || break
		sleep 1
	done
	grep -q "policy " "$LOG_DIR/politika.log" || fail "politika dugumu acilmadi: $(tail -2 "$LOG_DIR/politika.log")"
	grep -h "policy " "$LOG_DIR/politika.log" | cut -c1-220 | sed 's/^/[run_airsim]   /'
	[ "$IZLE" = 1 ] && ros2 run rqt_image_view rqt_image_view /eland/rl/gorus >"$LOG_DIR/izle_rl.log" 2>&1 &
	# rl_landing_mode is started after the takeoff (as rl_izle.sh does): started this early, while the
	# uXRCE-DDS session was still coming up, it failed to register ("Registration failed") and aborted
else
	for _ in $(seq 1 60); do
		grep -q "RegisterExtComponentReply" "$LOG_DIR/pipeline.log" 2>/dev/null && break
		sleep 1
	done
	grep -q "RegisterExtComponentReply" "$LOG_DIR/pipeline.log" && echo "[run_airsim]   mod PX4'e kaydedildi" ||
		echo "[run_airsim]   UYARI: mod kaydi gorunmedi -- $LOG_DIR/pipeline.log"
fi

# ------------------------------------------------------------ kalkis ve tetik (run_sim.sh ile ayni)
if [ -n "$TAKEOFF_ALT" ]; then
	echo "[run_airsim] kalkis: $TAKEOFF_ALT m"
	timeout 10 "$PX4_BIN/px4-param" set MIS_TAKEOFF_ALT "$TAKEOFF_ALT" >/dev/null 2>&1
	timeout 10 "$PX4_BIN/px4-commander" arm -f >/dev/null 2>&1
	sleep 2
	timeout 10 "$PX4_BIN/px4-commander" takeoff >/dev/null 2>&1
	for _ in $(seq 1 60); do
		alt=$(timeout 10 "$PX4_BIN/px4-listener" vehicle_local_position 2>/dev/null | grep -E "^\s+z:" | head -1 | tr -d ' z:')
		case "$alt" in -*) ;; *) alt="-0" ;; esac
		awk -v a="$alt" -v t="$TAKEOFF_ALT" 'BEGIN{exit !(-a > t*0.9)}' && break
		sleep 1
	done
	echo "[run_airsim]   irtifa $(echo "$alt" | tr -d '-') m"
fi
if [ -n "$HAVADA" ]; then
	# Air start: PX4 arms on the ground, so the vehicle climbed at the spawn and now flies to the target with
	# VEHICLE_CMD_DO_REPOSITION (PX4 holds there in Hold mode): across at the takeoff height, then to the
	# target height. The local origin stays at the spawn, so inis_sina.py's landing offsets are unchanged.
	IFS=, read -r H_N H_E H_ALT <<<"$HAVADA"
	ev() { timeout 10 "$PX4_BIN/px4-listener" home_position 2>/dev/null | awk -v k="$1:" '$1 == k {print $2; exit}'; }
	LAT0=$(ev lat); LON0=$(ev lon); ALT0=$(ev alt)
	[ -n "$LAT0" ] && [ -n "$LON0" ] && [ -n "$ALT0" ] || fail "PX4 ev konumu (home_position) okunamadi"
	konum() {
		timeout 10 "$PX4_BIN/px4-listener" vehicle_local_position 2>/dev/null |
			awk '$1 == "x:" && !a {x = $2; a = 1} $1 == "y:" && !b {y = $2; b = 1} $1 == "z:" && !c {z = $2; c = 1}
			     END {print x, y, z}'
	}
	hedefe_uc() {  # N E IRTIFA
		local ll amsl
		ll=$(python3 -c "import math, sys; la, lo, n, e = map(float, sys.argv[1:]); r = 6378137.0
print(f'{la + math.degrees(n / r):.8f} {lo + math.degrees(e / (r * math.cos(math.radians(la)))):.8f}')" "$LAT0" "$LON0" "$1" "$2")
		amsl=$(awk -v a="$ALT0" -v h="$3" 'BEGIN {printf "%.2f", a + h}')
		ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
			"{command: 192, param1: -1.0, param2: 1.0, param4: .nan, param5: ${ll% *}, param6: ${ll#* }, param7: $amsl, target_system: 1, target_component: 1, source_system: 255, source_component: 190, from_external: true}" \
			--qos-reliability best_effort --qos-durability transient_local >/dev/null 2>&1
	}
	vardi() {  # N E IRTIFA: within 2 m across and 1 m in height
		konum | awk -v n="$1" -v e="$2" -v h="$3" '{exit !(NF == 3 && sqrt(($1 - n)^2 + ($2 - e)^2) < 2.0 && (-$3 - h)^2 < 1.0)}'
	}
	echo "[run_airsim] havada baslangica uculuyor: ($H_N, $H_E) m, $H_ALT m"
	hedefe_uc "$H_N" "$H_E" "$TAKEOFF_ALT"
	for _ in $(seq 1 90); do vardi "$H_N" "$H_E" "$TAKEOFF_ALT" && break; sleep 1; done
	hedefe_uc "$H_N" "$H_E" "$H_ALT"
	for _ in $(seq 1 60); do vardi "$H_N" "$H_E" "$H_ALT" && break; sleep 1; done
	sleep 3      # settle into the hover the policy was trained to start from
	vardi "$H_N" "$H_E" "$H_ALT" || fail "havada hedefe varilamadi; konum $(konum)"
	echo "[run_airsim]   havada: konum $(konum) (x, y, z NED, dogma noktasina gore)"
fi
if [ -n "$RL_MODEL" ]; then
	for kayit in 1 2 3; do      # a registration attempted too early fails; try again after a pause
		ros2 run eland_rl_mode rl_landing_mode >"$LOG_DIR/rl_mod.log" 2>&1 &
		RLM_PID=$!
		for _ in $(seq 1 60); do
			grep -qE "RegisterExtComponentReply|Registration failed" "$LOG_DIR/rl_mod.log" 2>/dev/null && break
			kill -0 "$RLM_PID" 2>/dev/null || break
			sleep 1
		done
		grep -q "RegisterExtComponentReply" "$LOG_DIR/rl_mod.log" && break
		kill "$RLM_PID" 2>/dev/null; sleep 10
	done
	if grep -q "RegisterExtComponentReply" "$LOG_DIR/rl_mod.log"; then
		echo "[run_airsim]   RL modu PX4'e kaydedildi"
	else
		fail "RL modu PX4'e kaydolamadi: $(grep -v DEBUG "$LOG_DIR/rl_mod.log" | tail -2 | tr '\n' ' ')"
	fi
	if [ "$STATION" = true ]; then   # the station's "0" key then selects RL Landing (eland_airsim.rl_tetik)
		python3 -m eland_airsim.rl_tetik >"$LOG_DIR/rl_tetik.log" 2>&1 &
		RLT_PID=$!
		echo "[run_airsim]   istasyonda 0 tusu: RL Landing"
	fi
fi
if [ "$DO_TRIGGER" = 1 ] && [ -n "$RL_MODEL" ]; then
	echo "[run_airsim] RL Landing modu seciliyor..."
	nav_state() { timeout 10 "$PX4_BIN/px4-listener" vehicle_status 2>/dev/null | awk '$1 == "nav_state:" {print $2; exit}'; }
	for deneme in 1 2 3; do       # as rl_izle.sh: the mode asks for activation, nav_state confirms it
		ros2 topic pub -1 /eland/rl/etkinlestir std_msgs/msg/Bool "{data: true}" >/dev/null 2>&1
		sleep 2
		ID=$(grep -o 'requested activation (nav_state [0-9]*' "$LOG_DIR/rl_mod.log" | tail -1 | awk '{print $NF}')
		if [ -n "$ID" ] && [ "$(nav_state)" = "$ID" ]; then echo "[run_airsim]   RL Landing secildi (nav_state $ID)"; break; fi
	done
elif [ "$DO_TRIGGER" = 1 ]; then
	echo "[run_airsim] Emergency Landing modu seciliyor..."
	ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
		"{command: 100001, param1: 23.0, target_system: 1, target_component: 1, source_system: 255, source_component: 190, from_external: true}" \
		--qos-reliability best_effort --qos-durability transient_local >/dev/null 2>&1
fi
echo "[run_airsim] hazir. Kapatmak icin Ctrl+C."
wait "$LAUNCH_PID"
exit
}
