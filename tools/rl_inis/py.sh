#!/bin/bash
# ~/rl_inis altindaki bir python betigini RL ortamiyla calistir: bash ~/rl_inis/py.sh betik.py [arg...]
source $HOME/rl_inis/ortam.sh
cd $HOME/rl_inis && $RL_PY -u "$@"
