#!/bin/bash
# graphify sorgulari (ros2_ws grafi)
cd $HOME/ros2_ws
ls -la --time-style=+%d.%m graphify-out/graph.json | awk '{print "graf tarihi:", $6}'
for Q in "HUD overlay buttons landing law selection controller" "wind disturbance obstacle injection gazebo world" "rl landing mode policy node px4 mode selection"; do
	echo "=========== $Q"
	timeout 60 $HOME/graphify-venv/bin/graphify query "$Q" --budget 900 2>&1 | head -60
done
