#!/usr/bin/env python3
"""Start conditions of one episode, drawn from (world, seed).

    tools/veri/baslangic.py DUNYA_YAML TOHUM  ->  "x,y,z,r,p,yaw ALT OFSET"

Altitude 10-20 m and a lateral offset 0-4 m from the target's centre, as the
task asks -- except over W5's platform, where the offset is 6.5-8 m so the
aircraft takes off from the ground and its EKF origin stays there (otherwise
the 4 m difference being measured would vanish). Same (world, seed), same
start: the episode can be repeated. A windy twin (veri_w4_r2p5) draws from
its windless world's id, so the pair differs in the wind alone.

A start on any surface other than the ground or the target is drawn again
from the same stream: W8 seed 3 put the aircraft on the 0.52 m class-boundary
object, so its EKF origin and resting height sat on the object and every
ground-truth height was 0.5 m off. Starts that never hit one are unchanged.
"""
import math
import os
import random
import re
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dunya import Dunya  # noqa: E402


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
    # not on anything raised either (W5's target is the platform top)
    diger = [s for s in d['yuzeyler'] if s.get('ad') != d['hedef'] or float(s.get('z', 0.0)) > 0.1]
    for _ in range(100):
        if not any(Dunya._icinde(s, cx + r * math.cos(a), cy + r * math.sin(a)) for s in diger):
            break
        r = rng.uniform(lo, hi)
        a = rng.uniform(0.0, 2.0 * math.pi)
    print(f'{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f},0,0,0,{yaw:.3f} '
          f'{alt} {r:.2f}')


if __name__ == '__main__':
    main()
