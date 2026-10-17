"""AirSim (NED world, FRD body) <-> ROS / Gazebo (ENU world, FLU body) and the camera model.

AirSim reports positions in metres, x north, y east, z down, and body attitude as a quaternion of
the forward-right-down body frame in that world. Everything else in this project is ENU/FLU, so the
bridge converts once, here, and nothing downstream needs to know which simulator ran.
"""
import math

import numpy as np

#: ENU <- NED for world vectors, FLU <- FRD for body vectors (both are their own inverse)
NED_TO_ENU = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
FRD_TO_FLU = np.diag([1.0, -1.0, -1.0])


def quat_to_matrix(w, x, y, z):
    n = math.sqrt(w * w + x * x + y * y + z * z) or 1.0
    w, x, y, z = w / n, x / n, y / n, z / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def matrix_to_quat(R):
    """(w, x, y, z) of a rotation matrix, w >= 0."""
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = (0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s)
    else:
        i = int(np.argmax(np.diag(R)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
        v = [0.0, 0.0, 0.0]
        v[i] = 0.25 * s
        v[j] = (R[j, i] + R[i, j]) / s
        v[k] = (R[k, i] + R[i, k]) / s
        q = ((R[k, j] - R[j, k]) / s, *v)
    q = np.array(q)
    return tuple(q if q[0] >= 0 else -q)


def ned_pose_to_enu(px, py, pz, qw, qx, qy, qz):
    """AirSim pose (NED position, FRD-in-NED quaternion) -> ((x, y, z) ENU, (w, x, y, z) FLU-in-ENU)."""
    pos = NED_TO_ENU @ np.array([px, py, pz])
    R = NED_TO_ENU @ quat_to_matrix(qw, qx, qy, qz) @ FRD_TO_FLU
    return tuple(pos), matrix_to_quat(R)


def camera_matrix(width, height, hfov_deg):
    """Pinhole intrinsics of a camera with square pixels and the given horizontal FOV."""
    f = (width / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)
    return f, f, width / 2.0, height / 2.0
