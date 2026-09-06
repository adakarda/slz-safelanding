#!/bin/bash
# Run the same configuration over N randomly drawn worlds and write one CSV row
# per flight.
#
# Why this exists: every number in docs/DURUM.md up to now came from a single
# run of a pinned scenario. That is the right way to compare two settings, and
# the wrong way to claim the system works -- measured on identical settings,
# candidate jumps varied between 1 and 7 across repeats. A claim about the
# system needs a distribution; a claim about a change needs the pinned scene.
#
# Usage: tools/batch_run.sh N [OUT.csv] [node.param=value ...]
#   N       how many flights
#   OUT     where the rows go (default /tmp/eland_batch.csv)
# Every run draws its own spawn pose and its own mob layout from the run index,
# so the set is reproducible: run i always gets seed 1000+i.
set -o pipefail

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
N="${1:-10}"
OUT="${2:-/tmp/eland_batch.csv}"
shift 2 2>/dev/null || shift $#
EXTRA_PARAMS="$*"

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
cd "$WS_DIR" || exit 1
# shellcheck disable=SC1091
source install/setup.bash
export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH:-}"

cleanup() {
	pkill -f "gz sim" 2>/dev/null
	pkill -x px4 2>/dev/null
	pkill -f MicroXRCEAgent 2>/dev/null
	pkill -f "ros2 launch" 2>/dev/null
	for n in obstacle_driv tracker_no detector_no mapping_no perception_no \
		emergency_landing hud_no control_stat image_bridg run_scor; do
		pkill -f "$n" 2>/dev/null
	done
	# PX4 keeps its ports for a moment after it dies; starting the next run
	# too early gives no simulation at all and a row of zeros.
	sleep 8
}

echo "run,spawn_seed,mob_seed,$(echo 'landed,candidate_hz,candidate_msgs,invalid_frames,gaps_over_3s,site_jumps,transitions,aborts,descent_s,err_mean,err_abs_mean,err_rms,site_risk,site_clearance_m,site_area_m2,touchdown_err_m')" > "$OUT"

for i in $(seq 1 "$N"); do
	SEED=$((1000 + i))
	echo "=== kosu $i/$N (seed $SEED) ==="
	cleanup
	python3 "$WS_DIR/tools/make_params.py" /tmp/eland_batch_params.yaml \
		obstacle_driver.randomize_mobs=true \
		"obstacle_driver.mob_seed=$SEED" $EXTRA_PARAMS >/dev/null || continue

	"$WS_DIR/src/eland_sim/scripts/run_sim.sh" --seed "$SEED" --headless \
		--no-hud --auto --params /tmp/eland_batch_params.yaml \
		>"/tmp/eland_batch_run_$i.log" 2>&1 &
	RUN=$!
	sleep 32
	timeout 200 python3 "$WS_DIR/tools/run_scorer.py" 150 \
		>"/tmp/eland_batch_score_$i.txt" 2>&1
	kill -INT "$RUN" 2>/dev/null

	python3 - "$i" "$SEED" "/tmp/eland_batch_score_$i.txt" "$OUT" <<'PY'
import sys

run, seed, path, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
keys = ('landed candidate_hz candidate_msgs invalid_frames gaps_over_3s '
        'site_jumps transitions aborts descent_s err_mean err_abs_mean '
        'err_rms site_risk site_clearance_m site_area_m2 '
        'touchdown_err_m').split()
got = {}
with open(path, errors='ignore') as f:
    for line in f:
        if '=' in line and not line.startswith(' '):
            k, _, v = line.strip().partition('=')
            if k in keys:
                got[k] = v
row = [run, seed, seed] + [got.get(k, '') for k in keys]
with open(out, 'a') as f:
    f.write(','.join(row) + '\n')
print('  ' + ', '.join(f'{k}={got.get(k, "?")}'
                       for k in ('landed', 'descent_s', 'err_rms',
                                 'transitions', 'invalid_frames')))
PY
done

cleanup
echo "=== ozet ==="
python3 "$WS_DIR/tools/batch_summary.py" "$OUT"
