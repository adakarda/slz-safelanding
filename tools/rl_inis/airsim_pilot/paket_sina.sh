#!/bin/bash
cd $HOME/ros2_ws/src/eland_airsim && PYTHONPATH=$PWD:$PYTHONPATH $HOME/airsim-venv/bin/python -m pytest -q -p no:cacheprovider test 2>&1 | tail -4
source /opt/ros/jazzy/setup.bash && cd $HOME/ros2_ws && colcon build --packages-select eland_airsim 2>&1 | tail -3
