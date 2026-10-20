#!/bin/bash
# v3 olcumunu durdur (yalniz python sureci; cagiran kabuk etkilenmez)
for p in $(pgrep -f 'airsim_pilot/v3_(olc|tani)\.py'); do
	[ "$(cat /proc/$p/comm 2>/dev/null)" = python ] && kill $p && echo "durduruldu $p"
done
