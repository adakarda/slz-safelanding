#!/bin/bash
# F1 eslesme testi: sinif renkli dunya -> 25 m kalkis -> px4_tepki programi; eslesme.py kareleri puanlar.
#   bash ~/rl_inis/eslesme/kos.sh es1
AD=${1:-es1}
D=$HOME/rl_inis/eslesme; T=$HOME/rl_inis/tanilama; WS=$HOME/ros2_ws; PX4=$HOME/PX4-Autopilot
if pgrep -x px4 >/dev/null || pgrep -x ruby >/dev/null; then
	echo "Calisan bir sim var; once onu kapat."; exit 2
fi
for m in $HOME/eland_veri/modeller/*/; do
	ln -sfn "${m%/}" "$PX4/Tools/simulation/gz/models/$(basename "$m")"
done
source /opt/ros/jazzy/setup.bash
source $WS/install/setup.bash
source $HOME/rl_inis/ortam.sh
export GZ_IP=127.0.0.1
mkdir -p $D/$AD; rm -f $D/$AD/DUR
cd $WS
src/eland_sim/scripts/run_sim.sh --world orto_dji0097_sinif --model x500_seg_cam_rgb_down \
	--pose 0,0,0.1,0,0,0 --headless --no-hud --takeoff 25 >$D/${AD}_sim.log 2>&1 &
SIM=$!
bitir() { kill -TERM $ES 2>/dev/null; kill -TERM $SIM 2>/dev/null; for _ in $(seq 1 30); do kill -0 $SIM 2>/dev/null || break; sleep 1; done; echo "[eslesme] sim kapandi"; }
trap bitir EXIT
sleep 20
$RL_PY -u $D/eslesme.py $D/$AD 900 >$D/${AD}_eslesme.log 2>&1 &
ES=$!
echo "[eslesme] sim $SIM, eslesme $ES"
timeout 900 python3 -u $T/px4_tepki.py --ros-args -p cikti:=$D/$AD/ucus.npz 2>&1 | tee $D/${AD}_node.log
touch $D/$AD/DUR
for _ in $(seq 1 60); do kill -0 $ES 2>/dev/null || break; sleep 1; done
echo "[eslesme] sonuc:"; cat $D/${AD}_eslesme.log
