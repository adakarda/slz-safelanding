#!/bin/bash
P=$HOME/PX4-Autopilot/ROMFS/px4fmu_common/init.d-posix
echo "== px4-rc.simulator (none / mavlink)"; grep -n -i "simulator_mavlink\|PX4_SIM_HOST\|none\|4560" $P/px4-rc.simulator | head -20
echo "== 10016_none_iris"; head -20 $P/airframes/10016_none_iris
echo "== algi kamera konusu"; grep -rn "image_topic\|camera.*topic\|/camera" $HOME/ros2_ws/src/eland_sim/config/eland_params.yaml | head -8
grep -rn "create_subscription(.*Image\|declare_parameter('image" $HOME/ros2_ws/src/eland_perception 2>/dev/null | head -5; ls $HOME/ros2_ws/src
