#!/bin/bash
# AirSim istemcisi icin WSL venv: sistem paketleri gorunur; airsim bagimliliksiz + kendi msgpackrpc katmanimiz.
set -e
V=$HOME/airsim-venv
[ -d $V ] || python3 -m venv --system-site-packages $V
$V/bin/pip install -q msgpack setuptools wheel 2>&1 | grep -v pybind11 || true
S=$($V/bin/python -c "import site; print(site.getsitepackages()[0])")
mkdir -p $S/msgpackrpc && cp $HOME/rl_inis/airsim_pilot/msgpackrpc_shim.py $S/msgpackrpc/__init__.py
$V/bin/pip install -q airsim==1.8.1 --no-deps --no-build-isolation 2>&1 | grep -v pybind11 || true
$V/bin/python -c "import airsim, msgpack; print('airsim', airsim.__version__, 'msgpack', msgpack.version)"
echo "== airsim icinde msgpackrpc kullanimi"; grep -rn "msgpackrpc\." $S/airsim/*.py | grep -v "^.*#" | head -20
