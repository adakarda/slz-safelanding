"""Connecting to AirSim from WSL.

AirSim runs on Windows; from WSL 2 (NAT networking) Windows is the default gateway, 172.20.240.1 on
this machine. The airsim Python package needs the old msgpack-rpc-python, which does not run on
Python 3.10+; ~/airsim-venv carries data/msgpackrpc_shim.py installed as `msgpackrpc` instead.
"""
import subprocess

RPC_PORT = 41451


def windows_host():
    """The Windows host as seen from WSL: the default gateway; 127.0.0.1 if that cannot be read."""
    try:
        out = subprocess.run(['ip', 'route'], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return '127.0.0.1'
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == 'default' and parts[1] == 'via':
            return parts[2]
    return '127.0.0.1'


def connect(host='', port=RPC_PORT, timeout_s=10.0, multirotor=True):
    import airsim  # ~/airsim-venv; see the module docstring
    host = host or windows_host()
    cls = airsim.MultirotorClient if multirotor else airsim.VehicleClient
    client = cls(ip=host, port=port, timeout_value=timeout_s)
    client.confirmConnection()
    return client
