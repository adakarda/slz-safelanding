#!/bin/bash
# calisan run_airsim.sh kosusunu nazikce kapat (temizle tuzagi her seyi kapatir)
for p in $(pgrep -f 'eland_airsim/scripts/run_airsim.sh'); do
	[ "$p" = $$ ] && continue
	kill -TERM "$p" 2>/dev/null && echo "TERM $p"
done
for _ in $(seq 1 30); do pgrep -x px4 >/dev/null || break; sleep 1; done
pgrep -x px4 >/dev/null && echo "px4 hala acik" || echo "px4 kapali"
tasklist.exe 2>/dev/null | grep -i -E "airsimnh|cityenviron" || echo "AirSim kapali"
