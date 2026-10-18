"""Son PX4 ULog'unda nav_state degisimleri ve o anlardaki manuel cubuk degerleri (RL modu neden birakildi?).

    python3 mod_degisim.py LOG.ulg
"""
import sys

import numpy as np
from pyulog import ULog

u = ULog(sys.argv[1], message_name_filter_list=['vehicle_status', 'manual_control_setpoint', 'vehicle_local_position'])
vs = u.get_dataset('vehicle_status').data
mc = u.get_dataset('manual_control_setpoint').data
lp = u.get_dataset('vehicle_local_position').data
t0 = vs['timestamp'][0]
nav = vs['nav_state']
for i in np.nonzero(np.diff(nav))[0]:
    t = vs['timestamp'][i + 1]
    j = np.searchsorted(mc['timestamp'], t) - 1
    k = np.searchsorted(lp['timestamp'], t) - 1
    cubuk = {n: round(float(mc[n][j]), 2) for n in ('roll', 'pitch', 'yaw', 'throttle') if n in mc}
    print(f't {(t - t0) / 1e6:7.1f} s  nav {nav[i]} -> {nav[i + 1]}  irtifa {-lp["z"][k]:5.1f} m  cubuklar {cubuk}')
