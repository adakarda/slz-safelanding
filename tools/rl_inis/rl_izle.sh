#!/bin/bash
# RL kontrolcusunu Gazebo'da izle (GUI). Egitim bu surede duraklatilir, cikista devam eder.
#   bash ~/rl_inis/rl_izle.sh [baslangic_no 0-14] [model.zip]
# Pencereler: Gazebo, /eland/rl/gorus (politikanin gordugu + sectigi eylem), bu terminal.
K=${1:-0}
D=$HOME/rl_inis; WS=$HOME/ros2_ws; PX4=$HOME/PX4-Autopilot; PX4_BIN=$PX4/build/px4_sitl_default/bin
MODEL=${2:-}
if [ -z "$MODEL" ]; then
	if [ -f $D/kos/pilot_s0/model.zip ]; then MODEL=$D/kos/pilot_s0/model.zip
	else MODEL=$(ls -t $D/kos/pilot_s0/ckpt/*.zip | head -1); fi
fi
read -r _ X Y H YAWD < <(awk -v k="$K" '$1 == k' $D/f4/baslangiclar.txt)
if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null; then
	echo "Calisan bir sim var; once onu kapat."; exit 2
fi
O=$D/izle/$(date +%H%M%S)_b$K; mkdir -p $O

# egitimi duraklat (ana surec ve butun alt surecleri)
alt() { for c in $(pgrep -P "$1"); do echo "$c"; alt "$c"; done; }
TRAIN=$(pgrep -f '[e]land_rl.train' | head -1)
PIDS=""
if [ -n "$TRAIN" ]; then PIDS="$TRAIN $(alt $TRAIN)"; kill -STOP $PIDS; echo "[izle] egitim duraklatildi"; fi

SIM=""; MOD=""; POL=""; RQ=""
bitir() {
	echo "[izle] kapatiliyor..."
	for p in $RQ $POL $MOD; do kill -INT $p 2>/dev/null; done
	sleep 2
	for p in $RQ $POL $MOD; do kill -9 $p 2>/dev/null; done
	[ -n "$SIM" ] && kill -TERM $SIM 2>/dev/null
	for _ in $(seq 1 30); do [ -n "$SIM" ] && kill -0 $SIM 2>/dev/null || break; sleep 1; done
	[ -n "$PIDS" ] && kill -CONT $PIDS 2>/dev/null && echo "[izle] egitim devam ediyor"
}
trap bitir EXIT

for m in $HOME/eland_veri/modeller/*/; do
	ln -sfn "${m%/}" "$PX4/Tools/simulation/gz/models/$(basename "$m")"
done
source /opt/ros/jazzy/setup.bash
source $WS/install/setup.bash
source $D/ortam.sh
export GZ_IP=127.0.0.1
YAW=$(python3 -c "import math; print(round(math.radians($YAWD), 5))")
echo "[izle] model: $MODEL"
echo "[izle] baslangic $K: x $X, y $Y, $H m, yaw $YAWD deg; loglar $O"
cd $WS
src/eland_sim/scripts/run_sim.sh --world orto_dji0097 --model x500_seg_cam_rgb_down \
	--pose $X,$Y,0.1,0,0,$YAW --no-hud --takeoff $H >$O/sim.log 2>&1 &
SIM=$!
echo "[izle] sim aciliyor, kalkis bekleniyor (1-2 dk)..."
for _ in $(seq 1 300); do grep -q '\[run_sim\]   irtifa' $O/sim.log && break; sleep 1; done
grep '\[run_sim\]   irtifa' $O/sim.log || { echo "[izle] kalkis olmadi, $O/sim.log"; exit 3; }
ros2 run eland_rl_mode rl_landing_mode >$O/mod.log 2>&1 &
MOD=$!
$RL_PY -u -m eland_rl.policy_node --ros-args -p model_path:=$MODEL -p label_source:=gt \
	-p log_csv:=$O/politika.csv >$O/politika.log 2>&1 &
POL=$!
ros2 run rqt_image_view rqt_image_view /eland/rl/gorus >$O/rqt.log 2>&1 &
RQ=$!
for _ in $(seq 1 60); do grep -q 'policy ' $O/politika.log && grep -qi 'regist' $O/mod.log && break; sleep 1; done

nav_state() { "$PX4_BIN/px4-listener" vehicle_status 2>/dev/null | awk '$1 == "nav_state:" {print $2; exit}'; }
sec() {
	for deneme in 1 2 3; do
		ros2 topic pub -1 /eland/rl/etkinlestir std_msgs/msg/Bool "{data: true}" >/dev/null 2>&1
		sleep 2
		ID=$(grep -o 'requested activation (nav_state [0-9]*' $O/mod.log | tail -1 | awk '{print $NF}')
		[ -n "$ID" ] && [ "$(nav_state)" = "$ID" ] && { echo "[izle] RL Landing secildi (nav_state $ID)"; return; }
	done
	echo "[izle] mod secilemedi; $O/mod.log"
}
yerde() { "$PX4_BIN/px4-listener" vehicle_land_detected 2>/dev/null | grep -qE '^\s+landed: True'; }
kalk() {
	if ! yerde; then echo "[izle] drone havada; once insin (t yalniz yerdeyken)"; return 1; fi
	"$PX4_BIN/px4-commander" arm -f >/dev/null 2>&1; sleep 2
	"$PX4_BIN/px4-commander" takeoff >/dev/null 2>&1
	echo "[izle] kalkiyor ($H m)..."
	for _ in $(seq 1 60); do
		alt=$("$PX4_BIN/px4-listener" vehicle_local_position 2>/dev/null | grep -E "^\s+z:" | head -1 | tr -d ' z:')
		awk -v a="${alt:-0}" -v t="$H" 'BEGIN{exit !(-a > t*0.9)}' && break
		sleep 1
	done
	echo "[izle] irtifa $(echo "$alt" | tr -d '-') m"
}
echo
echo "[izle] Drone $H m'de. 3 s sonra RL Landing kendiliginden secilecek."
sleep 3
sec
echo "[izle] Politika suruyor; rqt penceresinde gordugu ve sectigi komut var. 5 m'de dikey inise gecer."
while true; do
	echo "[izle] t: indikten sonra ayni yerden yeniden kalk (RL kendiliginden secilir)   s: RL modunu yeniden sec   q: cik"
	read -r c || break
	case "$c" in
		q) break ;;
		t) kalk && { sleep 3; sec; } ;;
		s) sec ;;
		*) ;;
	esac
	grep -v DEBUG $O/mod.log | tail -n 2 | sed 's/^/[mod] /'
done
