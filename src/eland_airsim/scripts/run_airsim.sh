#!/bin/bash
# run_sim.sh'in AirSim karsiligi: Windows'ta AirSim, WSL'de PX4 SITL (none_iris) + uXRCE-DDS + kopru + algi zinciri.
#
#   src/eland_airsim/scripts/run_airsim.sh [--dunya AirSimNH] [--takeoff 25] [--trigger] [--no-hud]
#                                           [--station] [--px4-param K=V]... [--log-dir DIR] [--zorla]
#                                           [--yalniz-px4]   (yalniz AirSim + PX4; ROS 2 tarafi acilmaz)
#
# Gazebo'ya dokunmaz: eland_sim.launch.py aynen kullanilir (Gazebo kopruleri bosta bekler), PX4 ayri bir
# rootfs'te calisir (rootfs_airsim) ki Gazebo kosularinin kayitli parametreleri karismasin.
# PX4 parametreleri: run_sim.sh ile ayni politika (NAV_RCL_ACT=1) + istenenler; baska degisiklik yok.
set -u
WS_DIR=$(cd "$(dirname "$0")/../../.." && pwd)
PX4_DIR=$HOME/PX4-Autopilot
PX4_BIN=$PX4_DIR/build/px4_sitl_default/bin
AIRSIM_DIR=/mnt/c/Users/arda_/airsim
VENV=$HOME/airsim-venv
DUNYA=AirSimNH; TAKEOFF_ALT=""; DO_TRIGGER=0; HUD=true; HUD_VIEW=true; STATION=false; PX4_PARAMS=""; ZORLA=0
YALNIZ_PX4=0
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
	-h | --help) sed -n 2,11p "$0"; exit 0 ;;
	*) echo "bilinmeyen secenek: $1"; exit 2 ;;
	esac
	shift
done
fail() { echo "[run_airsim] HATA: $*"; exit 1; }
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
if [ -n "$BOS_MB" ] && [ "$BOS_MB" -lt 2500 ] && [ "$ZORLA" = 0 ]; then
	fail "Windows'ta 2.5 GB'tan az bos bellek var; egitimler bitince dene ya da --zorla"
fi
GW=$(ip route | awk '$1 == "default" {print $3; exit}')
[ -n "$GW" ] || fail "Windows adresi (varsayilan ag gecidi) bulunamadi"
mkdir -p "$LOG_DIR"
echo "[run_airsim] gunlukler: $LOG_DIR; Windows: $GW"

AIRSIM_PID=""; PX4_PID=""; AGENT_PID=""; KOPRU_PID=""; LAUNCH_PID=""; BEKCI_PID=""
temizle() {
	echo "[run_airsim] kapatiliyor..."
	[ -n "$BEKCI_PID" ] && kill "$BEKCI_PID" 2>/dev/null
	for p in $LAUNCH_PID $KOPRU_PID $AGENT_PID; do kill -INT "$p" 2>/dev/null; done
	sleep 2
	[ -n "$PX4_PID" ] && kill "$PX4_PID" 2>/dev/null
	for p in $LAUNCH_PID $KOPRU_PID $AGENT_PID $PX4_PID; do kill -9 "$p" 2>/dev/null; done
	pkill -x MicroXRCEAgent 2>/dev/null
	taskkill.exe /IM "$DUNYA.exe" /F >/dev/null 2>&1
	echo "[run_airsim] kapandi"
}
trap temizle EXIT INT TERM

# ------------------------------------------------------------ AirSim
AYAR_WIN='C:\Users\arda_\airsim\settings_px4.json'
python3 - "$WS_DIR/src/eland_airsim/config/settings_px4.json" "$AIRSIM_DIR/settings_px4.json" "$GW" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
s['Vehicles']['PX4']['LocalHostIp'] = sys.argv[3]
json.dump(s, open(sys.argv[2], 'w'), indent=2)
PY
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
	PX4_SYS_AUTOSTART=10016 PX4_SIM_MODEL=none_iris PX4_SIM_HOSTNAME="$GW" exec ../bin/px4 -d
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
"$PX4_BIN/px4-param" set NAV_RCL_ACT 1 >/dev/null 2>&1
for kv in $PX4_PARAMS; do
	"$PX4_BIN/px4-param" set "${kv%%=*}" "${kv#*=}" >/dev/null 2>&1 && echo "[run_airsim]   PX4 param $kv"
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
"$VENV/bin/python" -m eland_airsim.kopru --ros-args -p host:="$GW" >"$LOG_DIR/kopru.log" 2>&1 &
KOPRU_PID=$!
ros2 launch eland_sim eland_sim.launch.py hud:="$HUD" hud_view:="$HUD_VIEW" station:="$STATION" \
	bridge_colored:=false >"$LOG_DIR/pipeline.log" 2>&1 &
LAUNCH_PID=$!
for _ in $(seq 1 60); do
	grep -q "RegisterExtComponentReply" "$LOG_DIR/pipeline.log" 2>/dev/null && break
	sleep 1
done
grep -q "RegisterExtComponentReply" "$LOG_DIR/pipeline.log" && echo "[run_airsim]   mod PX4'e kaydedildi" ||
	echo "[run_airsim]   UYARI: mod kaydi gorunmedi -- $LOG_DIR/pipeline.log"

# ------------------------------------------------------------ kalkis ve tetik (run_sim.sh ile ayni)
if [ -n "$TAKEOFF_ALT" ]; then
	echo "[run_airsim] kalkis: $TAKEOFF_ALT m"
	"$PX4_BIN/px4-param" set MIS_TAKEOFF_ALT "$TAKEOFF_ALT" >/dev/null 2>&1
	"$PX4_BIN/px4-commander" arm -f >/dev/null 2>&1
	sleep 2
	"$PX4_BIN/px4-commander" takeoff >/dev/null 2>&1
	for _ in $(seq 1 60); do
		alt=$("$PX4_BIN/px4-listener" vehicle_local_position 2>/dev/null | grep -E "^\s+z:" | head -1 | tr -d ' z:')
		case "$alt" in -*) ;; *) alt="-0" ;; esac
		awk -v a="$alt" -v t="$TAKEOFF_ALT" 'BEGIN{exit !(-a > t*0.9)}' && break
		sleep 1
	done
	echo "[run_airsim]   irtifa $(echo "$alt" | tr -d '-') m"
fi
if [ "$DO_TRIGGER" = 1 ]; then
	echo "[run_airsim] Emergency Landing modu seciliyor..."
	ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
		"{command: 100001, param1: 23.0, target_system: 1, target_component: 1, source_system: 255, source_component: 190, from_external: true}" \
		--qos-reliability best_effort --qos-durability transient_local >/dev/null 2>&1
fi
echo "[run_airsim] hazir. Kapatmak icin Ctrl+C."
wait "$LAUNCH_PID"
