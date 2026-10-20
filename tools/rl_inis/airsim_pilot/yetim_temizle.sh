#!/bin/bash
# AirSim kosularindan kalan yetim ROS dugumlerini ada gore kapat (egitimlere dokunmaz).
for ad in hud_node detector_node mapping_node perception_node image_bridge tracker_node obstacle_driver \
	rl_landing_mode control_station rqt_image_view p_kestirici; do
	pkill -x "$ad" 2>/dev/null && echo "kapatildi: $ad"
done
pkill emergency_land 2>/dev/null && echo "kapatildi: emergency_landing_mode"
for p in $(pgrep -f 'eland_airsim\.kopru|v3_airsim\.py|eland_rl\.policy_node|eland_airsim\.inis_sina'); do
	[ "$p" = $$ ] || { kill "$p" 2>/dev/null && echo "kapatildi: $(tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | cut -c1-60) ($p)"; }
done
pkill -x MicroXRCEAgent 2>/dev/null && echo "kapatildi: MicroXRCEAgent"
sleep 2
free -m | sed -n 2p
