#!/bin/bash
W=$HOME/ros2_ws
echo "== run_sim.sh boyut"; wc -l $W/src/eland_sim/scripts/run_sim.sh
echo "== PX4 baslatma satirlari"; grep -n "px4_sitl\|bin/px4\|PX4_GZ\|PX4_SIM\|MicroXRCE\|uxrce\|ros2 launch\|ros_gz\|parameter_bridge\|use_sim_time" $W/src/eland_sim/scripts/run_sim.sh | head -30
echo "== launch dosyasi dugumleri"; grep -n "Node(\|package=\|executable=\|use_sim_time\|parameter_bridge\|gz" $W/src/eland_sim/launch/eland_sim.launch.py | head -40
echo "== algi segmentasyon konusu kullanimi"; grep -n "segmentation_topic\|use_gt\|kaynak\|mode" $W/src/eland_perception/eland_perception/perception_node.py | head -15
