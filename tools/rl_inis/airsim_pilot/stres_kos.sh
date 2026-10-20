#!/bin/bash
# RPC yuk testi: AirSim + PX4 (ucus yok), 6 dk koprunun yuku + ucuncu istemci, sonra kapat.
WS=$HOME/ros2_ws
LOG=$HOME/eland_veri/_gunlukler/airsim_stres_$(date +%H%M%S)
bash $WS/src/eland_airsim/scripts/run_airsim.sh --yalniz-px4 --log-dir $LOG >$LOG.out 2>&1 &
R=$!
for _ in $(seq 1 300); do grep -qE "hazir \(yalniz|HATA" $LOG.out 2>/dev/null && break; sleep 1; done
cat $LOG.out
PYTHONPATH=$WS/src/eland_airsim ~/airsim-venv/bin/python -m eland_airsim.rpc_stres --sure 360
kill -TERM $R; wait $R
echo "[stres] AirSim gunlugu son satirlar:"
tail -3 /mnt/c/Users/arda_/airsim/AirSimNH/AirSimNH/WindowsNoEditor/AirSimNH/Saved/Logs/AirSimNH.log | cut -c1-160
