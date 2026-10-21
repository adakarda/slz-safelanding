"""run_airsim.sh: every one-shot `ros2 topic pub -1` gets a 10 s timeout (25c, 22.10 00:30: AirSim froze, rl_landing_mode
exited, and `ros2 topic pub -1 /eland/rl/etkinlestir` waited 29 min for a subscriber; the batch's TERM could not act until
that foreground command ended). Atomic replace: a running batch keeps its old copy.

    python3 yama_pub_timeout.py
"""
import os

p = os.path.expanduser('~/ros2_ws/src/eland_airsim/scripts/run_airsim.sh')
s = open(p, encoding='utf-8').read()
n0 = s.count('ros2 topic pub -1 ')
s = s.replace('timeout 10 ros2 topic pub -1 ', 'ros2 topic pub -1 ')      # idempotent
s = s.replace('ros2 topic pub -1 ', 'timeout 10 ros2 topic pub -1 ')
tmp = p + '.yeni'
open(tmp, 'w', encoding='utf-8').write(s)
os.chmod(tmp, os.stat(p).st_mode)
os.replace(tmp, p)
print(f'{n0} ros2 topic pub -1 cagrisina timeout 10 eklendi')
