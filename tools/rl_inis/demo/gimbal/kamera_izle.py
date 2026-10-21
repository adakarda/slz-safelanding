"""While an AirSim run flies: once a second, the vehicle's and the downward camera's pitch and roll (degrees, from
AirSim's ground truth). Under a working gimbal the camera's stay fixed while the vehicle's move.

    ~/airsim-venv/bin/python kamera_izle.py [SURE_S]
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.expanduser('~/ros2_ws/src/eland_airsim'))
from eland_airsim import istemci  # noqa: E402


def euler(q):
    w, x, y, z = q.w_val, q.x_val, q.y_val, q.z_val
    roll = math.degrees(math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y)))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x)))))
    return pitch, roll


c = istemci.connect(istemci.windows_host())
son = time.time() + (float(sys.argv[1]) if len(sys.argv) > 1 else 600)
satir = 0
while time.time() < son:
    try:
        vp, vr = euler(c.simGetVehiclePose('PX4').orientation)
        kp, kr = euler(c.simGetCameraInfo('asagi', 'PX4').pose.orientation)
        print(f'{time.strftime("%H:%M:%S")} arac pitch {vp:6.1f} roll {vr:6.1f} | kamera pitch {kp:6.1f} roll {kr:6.1f}',
              flush=True)
        satir += 1
    except Exception as e:      # AirSim closing between runs
        print('baglanti yok:', type(e).__name__, flush=True)
        time.sleep(5)
        try:
            c = istemci.connect(istemci.windows_host())
        except Exception:
            pass
    time.sleep(1.0)
