#!/bin/bash
# F1 PX4 tepki olcumu, AirSim'de (Faz 4): run_airsim.sh -> 25 m kalkis -> px4_tepki.py -> kapat -> analiz.
#   bash ~/rl_inis/tanilama/kos_airsim.sh [ad]      (varsayilan airsim1)
# px4_tepki.py yalniz PX4 konularini kullanir (Gazebo'ya bagli degil), aynen calisir. Sonuc kos1 (Gazebo)
# ile karsilastirilir: tau_xy, a_max, gecikme, tau_z, egim.
AD=${1:-airsim1}
D=$HOME/rl_inis/tanilama; WS=$HOME/ros2_ws
LOG=$HOME/eland_veri/_gunlukler/airsim_tepki_$AD
bash "$WS/src/eland_airsim/scripts/run_airsim.sh" --takeoff 25 --no-hud --log-dir "$LOG" >"$D/${AD}_sim.log" 2>&1 &
SIM=$!
bitir() { kill -TERM $SIM 2>/dev/null; for _ in $(seq 1 40); do kill -0 $SIM 2>/dev/null || break; sleep 1; done; echo "[tanilama] sim kapandi"; }
trap bitir EXIT
for _ in $(seq 1 400); do
	grep -qE "hazir\. Kapatmak|HATA" "$D/${AD}_sim.log" 2>/dev/null && break
	kill -0 $SIM 2>/dev/null || break
	sleep 1
done
cat "$D/${AD}_sim.log"
grep -q "hazir\. Kapatmak" "$D/${AD}_sim.log" || { echo "[tanilama] sim hazir olmadi"; exit 1; }
source /opt/ros/jazzy/setup.bash
source $WS/install/setup.bash
export PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH
timeout 600 python3 -u $D/px4_tepki.py --ros-args -p cikti:=$D/$AD.npz >$D/${AD}_node.log 2>&1; grep -v Traceback $D/${AD}_node.log | grep INFO | tail -5
echo "[tanilama] dugum bitti"
bitir; trap - EXIT
cd $D && python3 analiz.py $AD.npz | tee ${AD}_analiz.txt
