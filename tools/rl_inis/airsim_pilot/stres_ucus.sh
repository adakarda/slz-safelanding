#!/bin/bash
# RPC yuk testi, arac havada: AirSim + PX4, 25 m kalkis, askida 6 dk kopru yuku + ucuncu istemci.
WS=$HOME/ros2_ws; PX4_BIN=$HOME/PX4-Autopilot/build/px4_sitl_default/bin
LOG=$HOME/eland_veri/_gunlukler/airsim_stres_ucus_$(date +%H%M%S)
bash $WS/src/eland_airsim/scripts/run_airsim.sh --yalniz-px4 --log-dir $LOG >$LOG.out 2>&1 &
R=$!
for _ in $(seq 1 300); do grep -qE "hazir \(yalniz|HATA" $LOG.out 2>/dev/null && break; sleep 1; done
cat $LOG.out
sleep 10
$PX4_BIN/px4-param set MIS_TAKEOFF_ALT 25 >/dev/null 2>&1
$PX4_BIN/px4-commander arm -f >/dev/null 2>&1; sleep 2; $PX4_BIN/px4-commander takeoff >/dev/null 2>&1
sleep 25
echo "[stres] irtifa: $($PX4_BIN/px4-listener vehicle_local_position 2>/dev/null | grep -E '^\s+z:' | head -1)"
PYTHONPATH=$WS/src/eland_airsim ~/airsim-venv/bin/python -m eland_airsim.rpc_stres --sure ${1:-360}
echo "[stres] AirSim sureci: $(tasklist.exe 2>/dev/null | grep -ci airsimnh)"
kill -TERM $R; wait $R
echo "[stres] AirSim gunlugu son satirlar:"
tail -4 /mnt/c/Users/arda_/airsim/AirSimNH/AirSimNH/WindowsNoEditor/AirSimNH/Saved/Logs/AirSimNH.log | cut -c1-160
