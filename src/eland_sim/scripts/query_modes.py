#!/usr/bin/env python3
"""Ask PX4 over MAVLink for its mode list, the way a GCS does.

QGroundControl builds its flight-mode menu from the AVAILABLE_MODES message
(MAVLink id 435): it sends MAV_CMD_REQUEST_MESSAGE with param2 = 0 meaning
"all modes", and PX4 streams one AVAILABLE_MODES per mode. Querying that
directly proves what any conforming GCS would display, without depending on a
particular QGC build being new enough to render it.
"""
import sys

from pymavlink import mavutil
from pymavlink.dialects.v20 import development as mavlink2

CONNECTION = sys.argv[1] if len(sys.argv) > 1 else 'udpin:0.0.0.0:14550'
MSG_AVAILABLE_MODES = 435

master = mavutil.mavlink_connection(CONNECTION, dialect='development')
print(f'waiting for heartbeat on {CONNECTION} ...')
hb = master.wait_heartbeat(timeout=30)
if hb is None:
    print('NO HEARTBEAT', file=sys.stderr)
    sys.exit(1)
print(f'connected: system {master.target_system}, component {master.target_component}')

master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 0,
    MSG_AVAILABLE_MODES,
    0,  # param2 = 0 -> request all modes
    0, 0, 0, 0, 0)

modes = {}
expected = None
deadline = 25
import time
start = time.time()
while time.time() - start < deadline:
    msg = master.recv_match(type='AVAILABLE_MODES', blocking=True, timeout=2)
    if msg is None:
        if modes and expected and len(modes) >= expected:
            break
        continue
    expected = msg.number_modes
    name = msg.mode_name
    if isinstance(name, bytes):
        name = name.decode('utf-8', 'replace')
    name = name.rstrip('\x00')
    modes[msg.mode_index] = (name, msg.custom_mode, msg.standard_mode, msg.properties)
    if len(modes) >= expected:
        break

if not modes:
    print('NO AVAILABLE_MODES RECEIVED', file=sys.stderr)
    sys.exit(2)

print(f'\nPX4 reports {expected} modes:\n')
print(f'{"idx":>4}  {"custom_mode":>12}  {"std":>4}  name')
print('-' * 60)
for idx in sorted(modes):
    name, custom, std, props = modes[idx]
    marker = '  <<<< EXTERNAL / ROS 2' if std == 0 and custom >= 23 else ''
    print(f'{idx:>4}  {custom:>12}  {std:>4}  {name}{marker}')
