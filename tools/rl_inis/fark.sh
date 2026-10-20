#!/bin/bash
cd $HOME/ros2_ws && git status --short | head && git diff src/eland_rl/eland_rl/train.py
