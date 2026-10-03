#!/usr/bin/env bash
# One recorded episode: sim up, recorder on, mode engaged, wait for touchdown,
# tear down.
#
#   tools/veri/kosu.sh TOHUM KOL DUNYA [node.param=value ...]
#
#   DUNYA     acik_alan (the existing world, random spawn from TOHUM) or an
#             island world from tools/veri/dunya_uret.py (veri_w3, veri_ada_t2005,
#             veri_w4_r2p5, ...); its start pose and altitude come from its yaml.
#
# Environment:
#   MODEL=NAME          another aircraft model (x500_seg_cam_down_ruzgar for wind)
#   POLITIKA="ARGS"     run tools/veri/politika.py ARGS and switch the mode's
#                       veri_toplama_kipi on (K1-K4). Add --devir-yok for W5.
#   BOZUCU="TUR SEV"    run tools/veri/bozucu.py and point the pipeline at its
#                       output (Asama 5)
#   EP_EK=TEXT          suffix for the episode id
#   KAYIT_SURE=S        stop recording after S wall seconds (default 240)
#   INIS_BEKLE=0        do not stop on touchdown (identification never lands)
#   BASLANGIC_IRTIFA=A  take off to A m instead of the world's / seed's value
#
# Refuses to start while another simulation is running: run_sim.sh kills any
# PX4/gz it finds and its cleanup kills every pipeline node by name, so
# starting next to someone's interactive session ends that session.
#
# Episodes go to $VERI_KOK/<kol>/<dunya>/<ep_id>/ (default ~/eland_veri).
set -o pipefail

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOHUM="${1:?tohum gerekli}"
KOL="${2:-kol0}"
DUNYA="${3:-acik_alan}"
shift 3 2>/dev/null || shift $#
EXTRA_PARAMS="$*"
VERI_KOK="${VERI_KOK:-$HOME/eland_veri}"
MODEL="${MODEL:-x500_seg_cam_down}"
EP_ID="${KOL}_${DUNYA}_t${TOHUM}${EP_EK:+_$EP_EK}"
OUT="$VERI_KOK/$KOL/$DUNYA/$EP_ID"
LOG="/tmp/veri_kosu_${EP_ID}.log"
PARAMS="/tmp/veri_params_${EP_ID}.yaml"

if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null; then
	echo "[veri] HATA: calisan bir simulasyon var; kosu baslatilmadi." >&2
	exit 2
fi

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
# shellcheck disable=SC1091
source "$WS_DIR/install/setup.bash"
export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH:-}"
export GZ_IP=127.0.0.1

# ---------------------------------------------------------------- world
if [ "$DUNYA" = "acik_alan" ]; then
	DUNYA_YAML="$WS_DIR/src/eland_sim/worlds/veri/acik_alan.yaml"
	GZ_WORLD="eland_test"
	WORLD_ARGS="--seed $TOHUM"
	DUNYA_PARAMS="obstacle_driver.randomize_mobs=true obstacle_driver.mob_seed=$TOHUM"
	ALT=$(python3 -c "import random; r = random.Random($TOHUM); print(round(r.uniform(10, 20), 1))")
else
	DUNYA_YAML=""
	for d in "$WS_DIR/src/eland_sim/worlds/veri" "$VERI_KOK/dunyalar"; do
		[ -f "$d/$DUNYA.yaml" ] && DUNYA_YAML="$d/$DUNYA.yaml" && break
	done
	[ -n "$DUNYA_YAML" ] || { echo "[veri] HATA: dunya yok: $DUNYA" >&2; exit 3; }
	GZ_WORLD="$DUNYA"
	DUNYA_PARAMS=$(python3 "$WS_DIR/tools/veri/dunya_parametreleri.py" "$DUNYA") || exit 3
	# Start pose and altitude from (world, seed), so repeats of a world differ.
	read -r POSE ALT OFSET < <(python3 "$WS_DIR/tools/veri/baslangic.py" "$DUNYA_YAML" "$TOHUM") ||
		exit 3
	WORLD_ARGS="--world $DUNYA --pose $POSE"
fi
ALT="${BASLANGIC_IRTIFA:-$ALT}"
MODEL_ARGS=""
[ "$MODEL" != "x500_seg_cam_down" ] && MODEL_ARGS="--model $MODEL"

INIS_ARG="--inince-dur"
[ "${INIS_BEKLE:-1}" = 0 ] && INIS_ARG=""

# ---------------------------------------------------------------- params
MODE_PARAMS=""
[ -n "${POLITIKA:-}" ] && MODE_PARAMS="emergency_landing_mode.veri_toplama_kipi=true"
BOZUK_TOPIC=""
if [ -n "${BOZUCU:-}" ]; then
	BOZUK_TOPIC="/eland/semantic_mask_bozuk"
	MODE_PARAMS="$MODE_PARAMS detector_node.mask_topic=$BOZUK_TOPIC mapping_node.mask_topic=$BOZUK_TOPIC hud_node.mask_topic=$BOZUK_TOPIC"
fi
# shellcheck disable=SC2086  # these are lists on purpose
python3 "$WS_DIR/tools/make_params.py" "$PARAMS" $DUNYA_PARAMS $MODE_PARAMS \
	$EXTRA_PARAMS >/dev/null || exit 1

mkdir -p "$OUT"
echo "[veri] $EP_ID: kalkis $ALT m, cikti $OUT"
# shellcheck disable=SC2086
"$WS_DIR/src/eland_sim/scripts/run_sim.sh" $WORLD_ARGS $MODEL_ARGS --headless --no-hud \
	--takeoff "$ALT" --auto --params "$PARAMS" >"$LOG" 2>&1 &
RUN=$!

# Everything that listens starts as soon as the ROS-PX4 bridge is up: before
# takeoff, so the resting height is measured on the ground.
for _ in $(seq 1 150); do
	grep -q "kopru kuruldu" "$LOG" 2>/dev/null && break
	kill -0 "$RUN" 2>/dev/null || break
	sleep 1
done
if ! grep -q "kopru kuruldu" "$LOG"; then
	echo "[veri] HATA: sim kalkmadi, bak: $LOG" >&2
	kill -TERM "$RUN" 2>/dev/null
	cp "$LOG" "$OUT/run_sim.log" 2>/dev/null
	exit 1
fi

KP=$(python3 -c "import yaml; p = yaml.safe_load(open('$PARAMS')); print(p['emergency_landing_mode']['ros__parameters'].get('descent_kp', 0.8))")
BOZUK_ARG=""
[ -n "$BOZUK_TOPIC" ] && BOZUK_ARG="--mask-bozuk-topic $BOZUK_TOPIC"
# shellcheck disable=SC2086
python3 "$WS_DIR/tools/veri/kaydedici.py" --cikti "$OUT" --ep-id "$EP_ID" \
	--dunya-id "$DUNYA" --dunya-yaml "$DUNYA_YAML" --gz-world "$GZ_WORLD" \
	--model "${MODEL}_0" --tohum "$TOHUM" --kol "$KOL" --kp "$KP" \
	--sure "${KAYIT_SURE:-240}" $INIS_ARG $BOZUK_ARG --maske-kaydet \
	>"$OUT/kaydedici.log" 2>&1 &
REC=$!
POL=""
if [ -n "${POLITIKA:-}" ]; then
	# shellcheck disable=SC2086
	python3 "$WS_DIR/tools/veri/politika.py" $POLITIKA --dunya-yaml "$DUNYA_YAML" \
		--gz-world "$GZ_WORLD" --model "${MODEL}_0" >"$OUT/politika.log" 2>&1 &
	POL=$!
fi
BOZ=""
if [ -n "${BOZUCU:-}" ]; then
	# shellcheck disable=SC2086
	python3 "$WS_DIR/tools/veri/bozucu.py" $BOZUCU --tohum "$TOHUM" >"$OUT/bozucu.log" 2>&1 &
	BOZ=$!
fi

# The conditions, written while PX4 is still up so its parameters can be read.
sleep 20
{
	echo "ep_id: $EP_ID"
	echo "kol: $KOL"
	echo "dunya: $DUNYA"
	echo "dunya_yaml: $DUNYA_YAML"
	echo "tohum: $TOHUM"
	echo "model: $MODEL"
	echo "baslangic_irtifasi_m: $ALT"
	echo "baslangic_ofset_m: ${OFSET:-null}"
	echo "dogus: '$(grep pose /tmp/eland_logs/spawn.txt 2>/dev/null | cut -d' ' -f2)'"
	python3 -c "import yaml; d = yaml.safe_load(open('$DUNYA_YAML')); print('negatif_ornek:', str(bool(d.get('negatif_ornek', False))).lower()); r = d.get('ruzgar') or {}; print('ruzgar_mps:', r.get('hiz_mps', 0.0))"
	echo "politika: '${POLITIKA:-}'"
	if [ -n "${POLITIKA:-}" ]; then
		case "$POLITIKA" in
		*--devir-yok*) echo "gt_devir: 'yok; Gazebo hedef yuksekligi < 2.5 m iken sabit 0.5 m/s, temas Gazebo dan (yalniz simulasyon, veri_toplama_kipi)'" ;;
		*) echo "gt_devir: 'COMMIT devri Gazebo hedef yuksekligi < 2.5 m ile (yalniz simulasyon, veri_toplama_kipi)'" ;;
		esac
	fi
	echo "bozucu: '${BOZUCU:-}'"
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
[ -n "$POL" ] && kill -TERM "$POL" 2>/dev/null
[ -n "$BOZ" ] && kill -TERM "$BOZ" 2>/dev/null
kill -TERM "$RUN" 2>/dev/null
wait "$RUN" 2>/dev/null
cp "$LOG" "$OUT/run_sim.log" 2>/dev/null
cp /tmp/eland_logs/pipeline.log "$OUT/pipeline.log" 2>/dev/null
# Belt and braces: the gz server can hang in its SIGTERM handler.
pkill -KILL -x ruby 2>/dev/null
tail -1 "$OUT/kaydedici.log"
