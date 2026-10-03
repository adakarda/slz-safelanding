#!/usr/bin/env python3
"""Start conditions of one episode, drawn from (world, seed).

    tools/veri/baslangic.py DUNYA_YAML TOHUM  ->  "x,y,z,r,p,yaw ALT OFSET"

Altitude 10-20 m and a lateral offset 0-4 m from the target's centre, as the
task asks -- except over W5's platform, where the offset is 6.5-8 m so the
aircraft takes off from the ground and its EKF origin stays there (otherwise
the 4 m difference being measured would vanish). Same (world, seed), same
start: the episode can be repeated. A windy twin (veri_w4_r2p5) draws from
its windless world's id, so the pair differs in the wind alone.
"""
import math
import random
import re
import sys

import yaml


def main():
    path, seed = sys.argv[1], int(sys.argv[2])
    d = yaml.safe_load(open(path))
    hedef = next(s for s in d['yuzeyler'] if s.get('ad') == d['hedef'])
    cx, cy = hedef['merkez']
    platform = any(s.get('ad') == 'platform' for s in d['yuzeyler'])
    lo, hi = (6.5, 8.0) if platform else (0.0, 4.0)
    temel = re.sub(r'_r[0-9p]+$', '', d['dunya_id'])  # dunya_uret.py's wind suffix
    rng = random.Random(f'{temel}:{seed}')
    alt = round(rng.uniform(10.0, 20.0), 1)
    r = rng.uniform(lo, hi)
    a = rng.uniform(0.0, 2.0 * math.pi)
    yaw = rng.uniform(-math.pi, math.pi)
    print(f'{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f},0,0,0,{yaw:.3f} '
          f'{alt} {r:.2f}')


if __name__ == '__main__':
    main()
