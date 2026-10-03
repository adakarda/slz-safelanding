#!/usr/bin/env bash
# One recorded landing: sim up, recorder on, mode engaged, wait for touchdown,
# tear down. Kol 0 (the existing system, unchanged) unless told otherwise.
#
#   tools/veri/kosu.sh TOHUM [KOL] [DUNYA] [node.param=value ...]
#
# Refuses to start while another simulation is running: run_sim.sh kills any
# PX4/gz it finds and its cleanup kills every pipeline node by name, so
# starting next to someone's interactive session ends that session.
#
# Episodes go to $VERI_KOK/<kol>/<dunya>/<ep_id>/ (default ~/eland_veri).
#
# Environment, for runs that are not ordinary landings:
#   KAYIT_SURE=S        stop recording after S wall seconds (default 240)
#   INIS_BEKLE=0        do not stop on touchdown (identification never lands)
#   BASLANGIC_IRTIFA=A  take off to A m instead of the seeded 10-20 m draw
set -o pipefail

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOHUM="${1:?tohum gerekli}"
KOL="${2:-kol0}"
DUNYA="${3:-acik_alan}"
shift 3 2>/dev/null || shift $#
EXTRA_PARAMS="$*"
VERI_KOK="${VERI_KOK:-$HOME/eland_veri}"
EP_ID="${KOL}_${DUNYA}_t${TOHUM}"
OUT="$VERI_KOK/$KOL/$DUNYA/$EP_ID"
LOG="/tmp/veri_kosu_${EP_ID}.log"
PARAMS="/tmp/veri_params_${EP_ID}.yaml"

if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null; then
	echo "[veri] HATA: calisan bir simulasyon var; kosu baslatilmadi." >&2
	exit 2
fi
if [ "$DUNYA" != "acik_alan" ]; then
	# New worlds need run_sim.sh to accept a world name -- an addition to
	# existing code that is waiting for approval (docs/VERI_TOPLAMA.md).
	echo "[veri] HATA: '$DUNYA' icin run_sim.sh --world gerekli (onay bekliyor)." >&2
	exit 3
fi

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
# shellcheck disable=SC1091
source "$WS_DIR/install/setup.bash"
export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH:-}"
export GZ_IP=127.0.0.1

# Start altitude 10-20 m, drawn from the seed so the episode can be repeated.
ALT=$(python3 -c "import random; r = random.Random($TOHUM); print(round(r.uniform(10, 20), 1))")
ALT="${BASLANGIC_IRTIFA:-$ALT}"
INIS_ARG="--inince-dur"
[ "${INIS_BEKLE:-1}" = 0 ] && INIS_ARG=""

# shellcheck disable=SC2086  # EXTRA_PARAMS is a list on purpose
python3 "$WS_DIR/tools/make_params.py" "$PARAMS" obstacle_driver.randomize_mobs=true \
	"obstacle_driver.mob_seed=$TOHUM" $EXTRA_PARAMS >/dev/null || exit 1

mkdir -p "$OUT"
echo "[veri] $EP_ID: kalkis $ALT m, cikti $OUT"
"$WS_DIR/src/eland_sim/scripts/run_sim.sh" --seed "$TOHUM" --headless --no-hud \
	--takeoff "$ALT" --auto --params "$PARAMS" >"$LOG" 2>&1 &
RUN=$!

# Recorder on as soon as the ROS-PX4 bridge is up: before takeoff, so the
# resting height is measured on the ground.
for _ in $(seq 1 150); do
	grep -q "kopru kuruldu" "$LOG" 2>/dev/null && break
	kill -0 "$RUN" 2>/dev/null || break
	sleep 1
done
if ! grep -q "kopru kuruldu" "$LOG"; then
	echo "[veri] HATA: sim kalkmadi, bak: $LOG" >&2
	kill -TERM "$RUN" 2>/dev/null
	exit 1
fi

KP=$(python3 -c "import yaml; p = yaml.safe_load(open('$PARAMS')); print(p['emergency_landing_mode']['ros__parameters'].get('descent_kp', 0.8))")
python3 "$WS_DIR/tools/veri/kaydedici.py" --cikti "$OUT" --ep-id "$EP_ID" \
	--dunya-id "$DUNYA" --tohum "$TOHUM" --kol "$KOL" --kp "$KP" \
	--sure "${KAYIT_SURE:-240}" $INIS_ARG --maske-kaydet >"$OUT/kaydedici.log" 2>&1 &
REC=$!

# The conditions, written while PX4 is still up so its parameters can be read.
sleep 20
{
	echo "ep_id: $EP_ID"
	echo "kol: $KOL"
	echo "dunya: $DUNYA"
	echo "tohum: $TOHUM"
	echo "baslangic_irtifasi_m: $ALT"
	echo "dogus: '$(grep pose /tmp/eland_logs/spawn.txt 2>/dev/null | cut -d' ' -f2)'"
	echo "ek_parametreler: '$EXTRA_PARAMS'"
	echo "params_dosyasi: $OUT/params.yaml"
	echo "git: $(git -C "$WS_DIR" describe --tags --always --dirty 2>/dev/null)"
	echo "px4_parametreleri:"
	for p in MPC_Z_V_AUTO_DN MPC_Z_VEL_MAX_DN MPC_Z_VEL_MAX_UP MPC_LAND_SPEED \
		MIS_TAKEOFF_ALT EKF2_HGT_REF NAV_RCL_ACT NAV_DLL_ACT COM_DISARM_LAND; do
		v=$("$HOME/PX4-Autopilot/build/px4_sitl_default/bin/px4-param" show "$p" 2>/dev/null |
			grep -E " $p " | sed 's/.*: //')
		echo "  $p: ${v:-bilinmiyor}"
	done
} >"$OUT/kosul.yaml"
cp "$PARAMS" "$OUT/params.yaml"

wait "$REC"
kill -TERM "$RUN" 2>/dev/null
wait "$RUN" 2>/dev/null
cp "$LOG" "$OUT/run_sim.log" 2>/dev/null
cp /tmp/eland_logs/pipeline.log "$OUT/pipeline.log" 2>/dev/null
# Belt and braces: the gz server can hang in its SIGTERM handler.
pkill -KILL -x ruby 2>/dev/null
tail -1 "$OUT/kaydedici.log"
