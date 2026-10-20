#!/bin/bash
S=$($HOME/airsim-venv/bin/python -c "import site; print(site.getsitepackages()[0])")
cp $HOME/rl_inis/airsim_pilot/msgpackrpc_shim.py $S/msgpackrpc/__init__.py
cd /tmp && $HOME/airsim-venv/bin/python $HOME/rl_inis/airsim_pilot/test_shim.py
