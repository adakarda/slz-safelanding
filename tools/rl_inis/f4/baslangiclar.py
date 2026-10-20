"""F4 starts: the evaluate.py starts of scene 0 (DJI_0097), so env and Gazebo fly the same 15 starts."""
import math
import sys

from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scenes import load_list

env = LandingEnv(load_list(sys.argv[1]), EnvConfig(max_t=30.0, randomise_dynamics=False))
for k in range(int(sys.argv[2]) if len(sys.argv) > 2 else 15):
    _, info = env.reset(seed=k, options={'scene_index': 0})
    x, y, h, yaw = info['start']
    print(f'{k} {x:.2f} {y:.2f} {h:.2f} {math.degrees(yaw):.1f}')
