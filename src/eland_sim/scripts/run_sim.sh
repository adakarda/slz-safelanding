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
# The px4-* clients talk to the running instance; used for parameters here and
# for arm/takeoff further down.
PX4_BIN="$PX4_DIR/build/px4_sitl_default/bin"
WS_DIR="${WS_DIR:-$HOME/ros2_ws}"
ROS_DISTRO_SETUP="/opt/ros/jazzy/setup.bash"
LOG_DIR="${LOG_DIR:-/tmp/eland_logs}"

POSE="0,0,0,0,0,0"
# Where the aircraft starts. Random unless something says otherwise, because
# a fixed spawn means every run tests the same twenty metres of grass -- and
# the landing logic was written to handle a world, not a neighbourhood.
# --scenario and --pose both pin it; --fixed pins it at the origin.
SPAWN_MODE="random"
SPAWN_SEED=""
SPAWN_BOUNDS=""
# A whole parameter file, and arbitrary launch arguments. Both exist for the
# comparison runs: the trajectory filter has to be measured against itself
# switched off, in the same world, without editing the tracked parameter file
# between the two halves of the experiment.
PARAMS_ARG=""
EXTRA_LAUNCH_ARGS=""
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

  (spawn is RANDOM unless one of --scenario / --pose / --fixed is given)
  --random-spawn     random start pose, clear of obstacles (the default)
  --seed N           same seed, same start pose -- for repeating a run
  --spawn-bounds x0,y0,x1,y1   area the random pose is drawn from
  --fixed            start at the world origin (old default)
  --scenario NAME    default | person | yard   (sets --pose)
                       default  open grass, site is right below the vehicle
                       person   3 m from a person, SORA shifts the site
                       yard     paved yard with trees and people, long approach
  --pose X,Y,Z,R,P,Y spawn pose, overrides --scenario
  --takeoff [ALT]    arm and take off once everything is up (default 18 m)
  --auto             --takeoff, then select the mode (full demo)
  --link-drop        --takeoff, then drop a real GCS link and let the PX4
                     failsafe select the mode on its own
  --params FILE      parameter YAML to launch with, instead of the installed
                     one. For comparison runs: same world, different settings.
  --launch-arg A:=B  extra launch argument, repeatable
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
		SPAWN_MODE="fixed"
		shift 2
		;;
	--pose)
		POSE="$2"
		SPAWN_MODE="fixed"
		shift 2
		;;
	--fixed)
		POSE="0,0,0,0,0,0"
		SPAWN_MODE="fixed"
		shift
		;;
	--random-spawn)
		SPAWN_MODE="random"
		shift
		;;
	--seed)
		SPAWN_SEED="$2"
		SPAWN_MODE="random"
		shift 2
		;;
	--spawn-bounds)
		SPAWN_BOUNDS="$2"
		SPAWN_MODE="random"
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
	--params)
		# Checked, because the failure is otherwise silent and expensive: a
		# params_file that does not exist leaves every node on the defaults
		# compiled into its own source, so the run completes, publishes, and
		# measures a scenario nobody configured. Cost of finding that out the
		# other way: several comparison runs where the obstacles were not
		# where the parameter file said they were.
		# (fail() is defined further down, after argument parsing.)
		if [ ! -f "$2" ]; then
			echo "[run_sim] HATA: --params: no such file: $2" >&2
			exit 1
		fi
		PARAMS_ARG="params_file:=$2"
		shift 2
		;;
	--launch-arg)
		EXTRA_LAUNCH_ARGS="$EXTRA_LAUNCH_ARGS $2"
		shift 2
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

# Rebuild the world from the parameters this run will actually use, before
# Gazebo reads it. The dynamic obstacles exist in two places -- their SDF and
# obstacle_driver's parameters -- and this is what stops those two drifting
# apart: change a start point in the YAML and the world already agrees on the
# next run, with no separate step to forget.
GEN_ARGS=""
if [ -n "$PARAMS_ARG" ]; then
	GEN_ARGS="--params ${PARAMS_ARG#params_file:=}"
fi
# shellcheck disable=SC2086
python3 "$(dirname "$0")/gen_world.py" $GEN_ARGS >/dev/null ||
	fail "dunya uretilemedi: scripts/gen_world.py"

# --------------------------------------------------------------- spawn pose
#
# After the world is generated, because the picker reads that world to find
# out what it has to stay away from, and the dynamic obstacles are only in it
# once the generator has run.
if [ "$SPAWN_MODE" = "random" ]; then
	SPAWN_ARGS=""
	[ -n "$SPAWN_SEED" ] && SPAWN_ARGS="$SPAWN_ARGS --seed $SPAWN_SEED"
	[ -n "$SPAWN_BOUNDS" ] && SPAWN_ARGS="$SPAWN_ARGS --bounds $SPAWN_BOUNDS"
	# shellcheck disable=SC2086
	SPAWN_OUT=$(python3 "$(dirname "$0")/pick_spawn.py" $SPAWN_ARGS 2>/dev/null)
	if [ -n "$SPAWN_OUT" ]; then
		POSE=$(echo "$SPAWN_OUT" | head -1)
		SPAWN_SEED=$(echo "$SPAWN_OUT" | tail -1)
		# Printed rather than buried: a run nobody can repeat is a run that
		# cannot be argued about.
		echo "[run_sim] rastgele dogus: pose $POSE  (seed $SPAWN_SEED)"
		echo "[run_sim]   ayni koşuyu tekrarlamak icin: --seed $SPAWN_SEED"
		echo "[run_sim]   ya da tam olarak: --pose $POSE"
	else
		echo "[run_sim] UYARI: dogus noktasi secilemedi, orijin kullaniliyor" >&2
	fi
fi

mkdir -p "$LOG_DIR"
# Kept with the run's own logs, so a recording and the pose it was made from
# do not have to be matched up by memory afterwards.
printf 'pose %s\nseed %s\nmode %s\n' "$POSE" "${SPAWN_SEED:--}" "$SPAWN_MODE" \
	>"$LOG_DIR/spawn.txt"
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

# --------------------------------------------------------- failsafe tuning
#
# Two parameters, both about the manual control link, both set because the
# defaults describe a radio transmitter and this link is a DDS bridge sharing
# a CPU with a software rasteriser.
#
# Measured: while the station streams a steady 20 Hz of ManualControlSetpoint,
# the rate PX4 actually accepts swings between 0 and 31 Hz -- it arrives in
# bursts with multi-second gaps. Every gap longer than COM_RC_LOSS_T makes PX4
# declare the transmitter lost, and with NAV_RCL_ACT at its default (Return)
# and this mode registered in Return's place, each of those declarations
# turned into an emergency landing. That is what "it lands on its own" and
# "taking manual control back does not stop it" both were.
#
#   NAV_RCL_ACT=1     Hold, not Return. A gap in the operator link should
#                     park the aircraft, not land it. The link-loss demo is
#                     unaffected: that runs on NAV_DLL_ACT (the GCS datalink),
#                     which is left at Return so a real GCS drop still brings
#                     up this mode.
#   COM_RC_LOSS_T=3   Three seconds of silence before calling it lost. Long
#                     enough to ride out the observed bursts, short enough to
#                     still be a failsafe.
#
# Both are simulation ergonomics. On real hardware with a real transmitter the
# defaults are the right numbers and these lines should not be copied.
"$PX4_BIN/px4-param" set NAV_RCL_ACT 1 >/dev/null 2>&1
"$PX4_BIN/px4-param" set COM_RC_LOSS_T 3 >/dev/null 2>&1

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
	$PARAMS_ARG $EXTRA_LAUNCH_ARGS \
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

# (PX4_BIN is set at the top of the file; the parameter tuning after startup
# needs it before this point.)

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
