#!/usr/bin/env bash
# Bring the whole emergency landing simulation up with one command.
#
# Starts PX4 SITL + Gazebo, the uXRCE-DDS agent and the ROS 2 pipeline in the
# right order, waiting for each to actually be ready rather than sleeping and
# hoping. Ctrl+C tears all of it down again -- which is the part that is
# genuinely tedious to do by hand, since PX4, the gz server, the gz GUI, the
# agent and five ROS nodes all have to go.
#
# PX4 runs with -d (no interactive pxh shell) because with everything sharing
# one terminal that prompt is unusable anyway. Arming and takeoff go through
# px4-commander instead; see --takeoff.
#
#   ./run_sim.sh                      open grass, GUI, no takeoff
#   ./run_sim.sh --scenario yard --auto
#   ./run_sim.sh --scenario person --link-drop
#   ./run_sim.sh --headless --auto    fastest, no Gazebo window

set -uo pipefail

PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"
WS_DIR="${WS_DIR:-$HOME/ros2_ws}"
ROS_DISTRO_SETUP="/opt/ros/jazzy/setup.bash"
LOG_DIR="${LOG_DIR:-/tmp/eland_logs}"

POSE="0,0,0,0,0,0"
HEADLESS=""
HUD="true"
STATION="true"
HUD_VIEW="false"
TAKEOFF_ALT=""
DO_TRIGGER=0
DO_LINK_DROP=0

usage() {
	cat <<'EOF'
run_sim.sh [options]

  --scenario NAME    default | person | yard   (sets --pose)
                       default  open grass, site is right below the vehicle
                       person   3 m from a person, SORA shifts the site
                       yard     paved yard with trees and people, long approach
  --pose X,Y,Z,R,P,Y spawn pose, overrides --scenario
  --takeoff [ALT]    arm and take off once everything is up (default 18 m)
  --auto             --takeoff, then select the mode (full demo)
  --link-drop        --takeoff, then drop a real GCS link and let the PX4
                     failsafe select the mode on its own
  --headless         no Gazebo window (faster; software rendering here)
  --no-hud           no HUD and no control station
  --hud-headless     publish /eland/hud but open no window at all
  --rqt              plain rqt_image_view on the HUD, no keyboard
  -h, --help
EOF
}

while [ $# -gt 0 ]; do
	case "$1" in
	--scenario)
		case "${2:-}" in
		default) POSE="0,0,0,0,0,0" ;;
		person) POSE="-6,-3,0,0,0,0" ;;
		yard) POSE="45,-45,0,0,0,0" ;;
		*)
			echo "unknown scenario '${2:-}'; use default, person or yard" >&2
			exit 1
			;;
		esac
		shift 2
		;;
	--pose)
		POSE="$2"
		shift 2
		;;
	--takeoff)
		# Optional numeric argument.
		if [[ "${2:-}" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
			TAKEOFF_ALT="$2"
			shift 2
		else
			TAKEOFF_ALT="18"
			shift
		fi
		;;
	--auto)
		TAKEOFF_ALT="${TAKEOFF_ALT:-18}"
		DO_TRIGGER=1
		shift
		;;
	--link-drop)
		TAKEOFF_ALT="${TAKEOFF_ALT:-18}"
		DO_LINK_DROP=1
		shift
		;;
	--headless)
		HEADLESS="1"
		shift
		;;
	--no-hud)
		HUD="false"
		HUD_VIEW="false"
		STATION="false"
		shift
		;;
	--rqt)
		STATION="false"
		HUD_VIEW="true"
		shift
		;;
	--hud-headless)
		# Keep publishing /eland/hud but do not open a window -- useful when
		# recording a bag or running over a connection without a display.
		HUD_VIEW="false"
		STATION="false"
		shift
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		echo "unknown option '$1'" >&2
		usage
		exit 1
		;;
	esac
done

# ---------------------------------------------------------------- teardown
cleanup() {
	echo
	echo "[run_sim] kapatiliyor..."
	# By name, not just by recorded PID: PX4 spawns the gz server and GUI
	# itself, and ros2 launch's children outlive the launcher if it is killed
	# on its own.
	pkill -f "[r]qt_image_view" 2>/dev/null
	pkill -x hud_node 2>/dev/null
	pkill -x detector_node 2>/dev/null
	pkill -x mapping_node 2>/dev/null
	pkill -x perception_node 2>/dev/null
	pkill -x image_bridge 2>/dev/null
	pkill emergency_land 2>/dev/null
	[ -n "${LAUNCH_PID:-}" ] && kill "$LAUNCH_PID" 2>/dev/null
	pkill -x MicroXRCEAgent 2>/dev/null
	pkill -x px4 2>/dev/null
	pkill -x ruby 2>/dev/null # the gz server and GUI are ruby wrappers
	sleep 1
	echo "[run_sim] bitti. Loglar: $LOG_DIR"
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------ prerequisites
fail() {
	echo "[run_sim] HATA: $*" >&2
	exit 1
}

[ -x "$PX4_DIR/build/px4_sitl_default/bin/px4" ] ||
	fail "PX4 derlenmemis: $PX4_DIR/build/px4_sitl_default/bin/px4 yok"
[ -f "$WS_DIR/install/setup.bash" ] ||
	fail "workspace derlenmemis: 'cd $WS_DIR && colcon build' calistir"
command -v MicroXRCEAgent >/dev/null ||
	fail "MicroXRCEAgent PATH'te yok"
[ -e "$PX4_DIR/Tools/simulation/gz/worlds/eland_test.sdf" ] ||
	fail "Gazebo varliklari bagli degil: scripts/link_px4_assets.sh calistir"

mkdir -p "$LOG_DIR"
# Anything left over from a previous run steals the ports and the topics.
pkill -x px4 2>/dev/null
pkill -x ruby 2>/dev/null
pkill -x MicroXRCEAgent 2>/dev/null
sleep 1

# -------------------------------------------------------------------- PX4
echo "[run_sim] PX4 + Gazebo baslatiliyor (pose $POSE${HEADLESS:+, headless})..."
(
	cd "$PX4_DIR/build/px4_sitl_default/rootfs" || exit 1
	HEADLESS="$HEADLESS" \
		PX4_GZ_WORLD=eland_test \
		PX4_SYS_AUTOSTART=4001 \
		PX4_SIM_MODEL=gz_x500_seg_cam_down \
		PX4_GZ_MODEL_POSE="$POSE" \
		GZ_IP=127.0.0.1 \
		exec ../bin/px4 -d
) >"$LOG_DIR/px4.log" 2>&1 &

for _ in $(seq 1 90); do
	grep -q "Startup script returned successfully" "$LOG_DIR/px4.log" 2>/dev/null && break
	sleep 1
done
grep -q "Startup script returned successfully" "$LOG_DIR/px4.log" ||
	fail "PX4 acilmadi, bak: $LOG_DIR/px4.log"
echo "[run_sim]   PX4 hazir"

# ------------------------------------------------------------------ agent
echo "[run_sim] uXRCE-DDS ajani baslatiliyor..."
MicroXRCEAgent udp4 -p 8888 >"$LOG_DIR/agent.log" 2>&1 &

# ROS's setup scripts read variables they have not set (AMENT_TRACE_SETUP_FILES
# among others), so nounset has to come off for the duration or sourcing dies.
set +u
# shellcheck source=/dev/null
source "$ROS_DISTRO_SETUP"
# shellcheck source=/dev/null
source "$WS_DIR/install/setup.bash"
set -u

for _ in $(seq 1 60); do
	ros2 topic list 2>/dev/null | grep -q vehicle_local_position && break
	sleep 1
done
ros2 topic list 2>/dev/null | grep -q vehicle_local_position ||
	fail "PX4 topic'leri gorunmedi, bak: $LOG_DIR/agent.log"
echo "[run_sim]   kopru kuruldu"

# --------------------------------------------------------------- pipeline
echo "[run_sim] algi zinciri + ucus modu baslatiliyor..."
ros2 launch eland_sim eland_sim.launch.py \
	hud:="$HUD" hud_view:="$HUD_VIEW" station:="$STATION" bridge_colored:=false \
	>"$LOG_DIR/pipeline.log" 2>&1 &
LAUNCH_PID=$!

for _ in $(seq 1 60); do
	grep -q "RegisterExtComponentReply" "$LOG_DIR/pipeline.log" 2>/dev/null && break
	sleep 1
done
if grep -q "RegisterExtComponentReply" "$LOG_DIR/pipeline.log" 2>/dev/null; then
	echo "[run_sim]   mod PX4'e kaydedildi"
else
	echo "[run_sim]   UYARI: mod kaydi gorunmedi -- $LOG_DIR/pipeline.log"
	echo "[run_sim]   (en sik sebep: px4_msgs / px4-ros2-interface-lib / PX4 surum uyusmazligi)"
fi

PX4_BIN="$PX4_DIR/build/px4_sitl_default/rootfs/../bin"

# --------------------------------------------------------------- takeoff
if [ -n "$TAKEOFF_ALT" ]; then
	echo "[run_sim] kalkis: $TAKEOFF_ALT m"
	"$PX4_BIN/px4-param" set MIS_TAKEOFF_ALT "$TAKEOFF_ALT" >/dev/null 2>&1
	# -f because without a GCS attached the preflight check refuses on
	# "no connection to the GCS", which is not a real problem in SITL.
	"$PX4_BIN/px4-commander" arm -f >/dev/null 2>&1
	sleep 2
	"$PX4_BIN/px4-commander" takeoff >/dev/null 2>&1
	for _ in $(seq 1 60); do
		alt=$("$PX4_BIN/px4-listener" vehicle_local_position 2>/dev/null |
			grep -E "^\s+z:" | head -1 | tr -d ' z:')
		case "$alt" in -*) ;; *) alt="-0" ;; esac
		# Close enough to the target to call it levelled off.
		awk -v a="$alt" -v t="$TAKEOFF_ALT" 'BEGIN{exit !(-a > t*0.9)}' && break
		sleep 1
	done
	echo "[run_sim]   irtifa $(echo "$alt" | tr -d '-') m"
fi

# --------------------------------------------------------------- trigger
if [ "$DO_TRIGGER" = 1 ]; then
	echo "[run_sim] Emergency Landing modu seciliyor..."
	ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \
		"{command: 100001, param1: 23.0, target_system: 1, target_component: 1, source_system: 255, source_component: 190, from_external: true}" \
		--qos-reliability best_effort --qos-durability transient_local >/dev/null 2>&1
fi

if [ "$DO_LINK_DROP" = 1 ]; then
	echo "[run_sim] gercek GCS baglantisi kuruluyor, sonra kesilecek..."
	python3 "$WS_DIR/src/eland_sim/scripts/gcs_link_drop.py" 20
	echo "[run_sim] baglanti koptu. PX4 failsafe'i ~16 s icinde modu getirmeli"
	echo "[run_sim]   (COM_DL_LOSS_T 10 s + PX4'un 5 s bekleme suresi)"
fi

# ------------------------------------------------------------------- done
cat <<EOF

  Hazir.$([ "$STATION" = true ] && echo " Kontrol istasyonu acildi -- ucurmak icin o pencereye tikla." )

  Durum akisi icin baska bir terminalde:

    source $ROS_DISTRO_SETUP && source $WS_DIR/install/setup.bash
    ros2 topic echo /eland/state

  Modu elle tetiklemek icin:

    ros2 topic pub -1 /fmu/in/vehicle_command px4_msgs/msg/VehicleCommand \\
      "{command: 100001, param1: 23.0, target_system: 1, target_component: 1, \\
        source_system: 255, source_component: 190, from_external: true}" \\
      --qos-reliability best_effort --qos-durability transient_local

  Loglar: $LOG_DIR    Kapatmak icin: Ctrl+C

EOF

# Hold the terminal so the trap fires on Ctrl+C rather than everything being
# orphaned the moment this script returns.
wait "$LAUNCH_PID"
