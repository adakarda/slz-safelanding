#!/bin/bash
# inis_sina.sh toplu kosusunu ve icindeki run_airsim'i durdur
for p in $(pgrep -f 'eland_airsim/scripts/inis_sina.sh'); do [ "$p" = $$ ] || kill -TERM "$p" 2>/dev/null && echo "TERM toplu $p"; done
pkill -f 'eland_airsim.inis_sina' 2>/dev/null
bash ~/rl_inis/airsim_pilot/kosu_durdur.sh
