#!/bin/bash
# Yalniz yeni paketleri derle: eland_rl_mode (C++) ve eland_rl (python).
source /opt/ros/jazzy/setup.bash
cd $HOME/ros2_ws
source install/setup.bash
colcon build --packages-select eland_rl_mode eland_rl --event-handlers console_direct- 2>&1 | tail -25
