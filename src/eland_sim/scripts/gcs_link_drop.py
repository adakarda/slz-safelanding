#!/usr/bin/env python3
"""Simulate the scenario the project is actually about: the operator link dies.

Rather than injecting a synthetic fault, this connects as a real GCS, sends
real heartbeats for a while so PX4 genuinely has a data link, and then stops.
After COM_DL_LOSS_T seconds PX4's data-link-loss failsafe fires and takes the
action in NAV_DLL_ACT -- which, with the Emergency Landing mode registered as
a replacement for Return, should bring up the ROS 2 mode instead of an RTL.

Usage: gcs_link_drop.py <seconds_of_link>
"""
import sys
import time

from pymavlink import mavutil

HOLD_S = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0

# 14550 is where PX4 *sends*; 18570 is where its "Normal" mavlink instance
# listens. Heartbeats aimed at 14550 are never seen by the autopilot, so the
# link it is meant to notice losing never exists in the first place.
master = mavutil.mavlink_connection('udpout:127.0.0.1:18570', source_system=255,
                                    source_component=190)

print(f'sending GCS heartbeats for {HOLD_S:.0f} s ...')
end = time.time() + HOLD_S
beats = 0
seen_vehicle = False
while time.time() < end:
    master.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0,
        mavutil.mavlink.MAV_STATE_ACTIVE)
    beats += 1
    if not seen_vehicle and master.recv_match(type='HEARTBEAT', blocking=False):
        seen_vehicle = True
        print('  vehicle heartbeat received -- link is two-way')
    time.sleep(0.25)

if not seen_vehicle:
    print('  WARNING: no vehicle heartbeat; the link may be one-way')

print(f'sent {beats} heartbeats; LINK DROPPED at {time.strftime("%H:%M:%S")}')
