"""How far from straight down the downward camera's optical axis points, next to the vehicle's tilt (degrees).
Euler angles are degenerate when looking straight down, so the axis itself is measured. 20 samples, 0.5 s apart.

    ~/airsim-venv/bin/python eksen_olc.py
"""
import math
import os
import sys
import time

sys.path.insert(0, os.path.expanduser('~/ros2_ws/src/eland_airsim'))
from eland_airsim import istemci  # noqa: E402


def eksen(q, v):
    """Rotate the body vector v by quaternion q (AirSim w, x, y, z)."""
    w, x, y, z = q.w_val, q.x_val, q.y_val, q.z_val
    vx, vy, vz = v
    # q * v * q^-1
    ix = w * vx + y * vz - z * vy
    iy = w * vy + z * vx - x * vz
    iz = w * vz + x * vy - y * vx
    iw = -x * vx - y * vy - z * vz
    return (ix * w + iw * -x + iy * -z - iz * -y,
            iy * w + iw * -y + iz * -x - ix * -z,
            iz * w + iw * -z + ix * -y - iy * -x)


def acidan(vec, hedef):
    d = sum(a * b for a, b in zip(vec, hedef)) / math.sqrt(sum(a * a for a in vec))
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


c = istemci.connect(istemci.windows_host())
for _ in range(20):
    arac = eksen(c.simGetVehiclePose('PX4').orientation, (0.0, 0.0, 1.0))           # body z (down) in NED
    q = c.simGetCameraInfo('asagi', 'PX4').pose.orientation
    kam = eksen(q, (1.0, 0.0, 0.0))                     # camera optical axis
    ust = eksen(q, (0.0, 0.0, -1.0))                    # image up (camera -Z) in the world
    print(f'arac egimi {acidan(arac, (0, 0, 1)):5.1f} | kamera ekseninin dikeyden sapmasi {acidan(kam, (0, 0, 1)):5.1f} | '
          f'goruntunun ustu {math.degrees(math.atan2(ust[1], ust[0])):7.1f} derece (kuzeyden)', flush=True)
    time.sleep(0.5)
