#!/bin/bash
# F4: tek Gazebo + PX4 kosusu, pilot politika ile.
#   bash kos_tek.sh AD X Y H YAW_DEG [gt|topic] [MODEL]
# Sim (headless, HUD yok) -> H m kalkis -> RL Landing modu + politika dugumu -> mod secimi -> inis -> kapat.
AD=$1; X=$2; Y=$3; H=$4; YAWD=$5; SRC=${6:-gt}
MODEL=${7:-$HOME/rl_inis/kos/pilot_s0/model.zip}
O=$HOME/rl_inis/f4/kos/$AD; WS=$HOME/ros2_ws; PX4=$HOME/PX4-Autopilot; PX4_BIN=$PX4/build/px4_sitl_default/bin
if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null; then
	echo "Calisan bir sim var; once onu kapat."; exit 2
fi
rm -rf $O; mkdir -p $O
for m in $HOME/eland_veri/modeller/*/; do
	ln -sfn "${m%/}" "$PX4/Tools/simulation/gz/models/$(basename "$m")"
done
source /opt/ros/jazzy/setup.bash
source $WS/install/setup.bash
source $HOME/rl_inis/ortam.sh
export GZ_IP=127.0.0.1
YAW=$(python3 -c "import math; print(round(math.radians($YAWD), 5))")
cd $WS
src/eland_sim/scripts/run_sim.sh --world orto_dji0097 --model x500_seg_cam_rgb_down \
	--pose $X,$Y,0.1,0,0,$YAW --headless --no-hud --takeoff $H >$O/sim.log 2>&1 &
SIM=$!
MOD=""; POL=""
bitir() {
	for p in $POL $MOD; do kill -INT $p 2>/dev/null; done
	sleep 2
	for p in $POL $MOD; do kill -9 $p 2>/dev/null; done
	kill -TERM $SIM 2>/dev/null
	for _ in $(seq 1 30); do kill -0 $SIM 2>/dev/null || break; sleep 1; done
}
trap bitir EXIT
for _ in $(seq 1 300); do grep -q '\[run_sim\]   irtifa' $O/sim.log && break; sleep 1; done
grep '\[run_sim\]   irtifa' $O/sim.log || { echo "SONUC $AD kalkis_yok"; exit 3; }
ros2 run eland_rl_mode rl_landing_mode >$O/mod.log 2>&1 &
MOD=$!
$RL_PY -u -m eland_rl.policy_node --ros-args -p model_path:=$MODEL -p label_source:=$SRC \
	-p log_csv:=$O/politika.csv >$O/politika.log 2>&1 &
POL=$!
for _ in $(seq 1 60); do grep -q 'policy ' $O/politika.log && grep -qi 'regist' $O/mod.log && break; sleep 1; done
sleep 3
nav_state() { "$PX4_BIN/px4-listener" vehicle_status 2>/dev/null | awk '$1 == "nav_state:" {print $2; exit}'; }
SECILDI=0
for deneme in 1 2 3 4; do
	ros2 topic pub -1 /eland/rl/etkinlestir std_msgs/msg/Bool "{data: true}" >/dev/null 2>&1
	sleep 2
	ID=$(grep -o 'requested activation (nav_state [0-9]*' $O/mod.log | tail -1 | awk '{print $NF}')
	NS=$(nav_state)
	echo "[f4] mod secimi deneme $deneme: hedef ${ID:-?}, nav_state ${NS:-?}"
	if [ -n "$ID" ] && [ "$NS" = "$ID" ]; then SECILDI=1; break; fi
done
[ $SECILDI = 1 ] || { echo "SONUC $AD mod_secilemedi"; exit 4; }
date +%s.%N >$O/etkin_t
SONUC=sure_doldu
for _ in $(seq 1 120); do
	if "$PX4_BIN/px4-listener" vehicle_land_detected 2>/dev/null | grep -qE '^\s+landed: True'; then SONUC=indi; break; fi
	sleep 1
done
sleep 2
echo "SONUC $AD $SONUC"
