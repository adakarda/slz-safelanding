#!/bin/bash
# Faz 2 sinamasi: AirSim + PX4'u (run_airsim.sh --yalniz-px4) ac, eland_airsim.px4_sina ile kalk-as-in, kapat.
#   src/eland_airsim/scripts/px4_sina.sh [run_airsim.sh secenekleri, ornek --zorla] [-- px4_sina secenekleri]
WS=$(cd "$(dirname "$0")/../../.." && pwd)
LOG=$HOME/eland_veri/_gunlukler/airsim_sina_$(date +%Y%m%d_%H%M%S)
mkdir -p "$LOG"
RA=(); while [ $# -gt 0 ] && [ "$1" != -- ]; do RA+=("$1"); shift; done; [ "${1:-}" = -- ] && shift
bash "$WS/src/eland_airsim/scripts/run_airsim.sh" --yalniz-px4 --log-dir "$LOG/calisma" "${RA[@]}" >"$LOG/run_airsim.out" 2>&1 &
R=$!
for _ in $(seq 1 300); do
	grep -q "hazir (yalniz" "$LOG/run_airsim.out" && break
	kill -0 $R 2>/dev/null || break
	sleep 1
done
cat "$LOG/run_airsim.out"
if ! grep -q "hazir (yalniz" "$LOG/run_airsim.out"; then
	kill -TERM $R 2>/dev/null; wait $R; tail -30 "$LOG/calisma/px4.log" 2>/dev/null; exit 1
fi
sleep 10   # GPS ve EKF otursun
PYTHONPATH="$WS/src/eland_airsim:${PYTHONPATH:-}" "$HOME/airsim-venv/bin/python" -m eland_airsim.px4_sina --out "$LOG/sina.json" "$@"
kill -TERM $R 2>/dev/null; wait $R
echo "--- px4.log uyari/hata (ilk 25)"
grep -iE "fail|error|warn|reject|denied" "$LOG/calisma/px4.log" | head -25
echo "gunlukler: $LOG"
