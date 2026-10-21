"""Gimbal with a fixed heading: the image is north-up whatever the nose does, so policy_node builds the observation
from a level camera facing north and turns the policy's image-relative actions into world velocities with that same
heading (a multicopter moves in any direction whatever its nose). Gimbal off: unchanged.

    python3 yama_gimbal2.py
"""
import os

p = os.path.expanduser('~/ros2_ws/src/eland_rl/eland_rl/policy_node.py')
s = open(p, encoding='utf-8').read()


def rep(old, new):
    global s
    if new in s:
        return
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep("        p('gimbal', False)          # the camera on a stabilised gimbal: level, heading follows the vehicle\n",
    "        p('gimbal', False)          # the camera on a stabilised gimbal: level, its heading fixed in the world\n"
    "        p('gimbal_yaw_enu_deg', 90.0)   # that heading, ENU (90 = north: AirSim gimbal Yaw 0)\n")
rep("        self.gimbal = bool(g('gimbal'))\n",
    "        self.gimbal = bool(g('gimbal'))\n"
    "        self.gimbal_yaw = math.radians(float(g('gimbal_yaw_enu_deg')))\n")
rep("        Rk = rotation((0.0, 0.0, 1.0), math.atan2(R[1, 0], R[0, 0])) if self.gimbal else R\n",
    "        Rk = rotation((0.0, 0.0, 1.0), self.gimbal_yaw) if self.gimbal else R\n")
rep("        yaw = math.atan2(R[1, 0], R[0, 0])\n"
    "        if a == 9:\n",
    "        yaw = math.atan2(R[1, 0], R[0, 0])\n"
    "        yaw_k = self.gimbal_yaw if self.gimbal else yaw      # the image's up: actions are relative to it\n"
    "        if a == 9:\n")
rep("            v_enu = np.array([math.cos(yaw) * bx - math.sin(yaw) * by, math.sin(yaw) * bx + math.cos(yaw) * by,\n",
    "            v_enu = np.array([math.cos(yaw_k) * bx - math.sin(yaw_k) * by, math.sin(yaw_k) * bx + math.cos(yaw_k) * by,\n")
tmp = p + '.yeni'
open(tmp, 'w', encoding='utf-8').write(s)
os.replace(tmp, p)
print('yamandi: policy_node.py')
