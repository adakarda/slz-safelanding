#!/bin/bash
P=$HOME/PX4-Autopilot
cd $P && echo "PX4: $(git describe --tags 2>/dev/null)"
ls ROMFS/px4fmu_common/init.d-posix/airframes/ | grep -iE "none|iris" | head
ls src/modules/simulation/ 2>/dev/null
grep -rn "4560" src/modules/simulation/simulator_mavlink/*.cpp 2>/dev/null | head -3
grep -n "PX4_SIM_HOSTNAME\|PX4_SIM_HOST_ADDR" -r src/modules/simulation/simulator_mavlink/ 2>/dev/null | head -3
ls build/px4_sitl_default/bin/px4 2>/dev/null && echo "sitl derlemesi var"
grep -n "simulator_mavlink\|SIMULATOR" boards/px4/sitl/default.px4board 2>/dev/null | head
echo "== ROS"; ls /opt/ros/jazzy/share | grep -iE "airsim|image_transport$|cv_bridge" 
echo "== WSL ag"; ip route | head -2; grep nameserver /etc/resolv.conf; cat /mnt/c/Users/arda_/.wslconfig 2>/dev/null
