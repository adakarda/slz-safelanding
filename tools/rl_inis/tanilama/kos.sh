#!/bin/bash
# F1 PX4 tepki olcumu: sim (headless, HUD yok) -> 25 m kalkis -> px4_tepki.py -> kapat.
#   bash ~/rl_inis/tanilama/kos.sh kos1
AD=${1:-kos1}
D=$HOME/rl_inis/tanilama; WS=$HOME/ros2_ws; PX4=$HOME/PX4-Autopilot
if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null; then
	echo "Calisan bir sim var; once onu kapat."; exit 2
fi
for m in $HOME/eland_veri/modeller/*/; do
	ln -sfn "${m%/}" "$PX4/Tools/simulation/gz/models/$(basename "$m")"
done
source /opt/ros/jazzy/setup.bash
source $WS/install/setup.bash
export GZ_IP=127.0.0.1
cd $WS
src/eland_sim/scripts/run_sim.sh --world orto_dji0097 --model x500_seg_cam_rgb_down \
	--pose 0,0,0.1,0,0,0 --headless --no-hud --takeoff 25 >$D/${AD}_sim.log 2>&1 &
SIM=$!
bitir() { kill -TERM $SIM 2>/dev/null; for _ in $(seq 1 30); do kill -0 $SIM 2>/dev/null || break; sleep 1; done; echo "[tanilama] sim kapandi"; }
trap bitir EXIT
echo "[tanilama] sim pid $SIM, log $D/${AD}_sim.log"
timeout 900 python3 -u $D/px4_tepki.py --ros-args -p cikti:=$D/$AD.npz 2>&1 | tee $D/${AD}_node.log
echo "[tanilama] dugum bitti (kod ${PIPESTATUS[0]})"
