"""Random air start for run_airsim.sh --havada rastgele and for batch lists.

    python3 havada_sec.py [--tohum N] [--baslangic X,Y] [--csv SPAWNS.csv] [--n 10 --cikti LIST.csv]

The vehicle cannot be born in the air: PX4 arms on the ground. So a spawn point is taken from the known
clear ground points (SPAWNS.csv, the Faz 3 starts; or --baslangic), the vehicle climbs there, and flies to a
target drawn around it: 10..--yaricap m away, at --irtifa (20..30 m, the training's start height). The target
must stay --sinir m inside the ortho map (AirSimNH: +-400 m around PlayerStart) so landings can be scored.

One start prints "X,Y N,E,ALT": spawn (NED m from PlayerStart) and target (NED m from the spawn, height m).
--n writes a list instead: x_ned,y_ned,hedef_n,hedef_e,irtifa (inis_sina.sh reads it).
"""
import argparse
import csv
import math
import os
import random


def spawns(path):
    if not path or not os.path.exists(path):
        return [(0.0, 0.0)]
    with open(path) as f:
        return [(float(r['x_ned']), float(r['y_ned'])) for r in csv.DictReader(f)]


def draw(rng, pts, radius, alt, bound):
    for _ in range(1000):
        x, y = rng.choice(pts)
        ang, d = rng.uniform(0, 2 * math.pi), math.sqrt(rng.uniform(10.0 ** 2, radius ** 2))
        n, e = d * math.cos(ang), d * math.sin(ang)
        if abs(x + n) <= bound and abs(y + e) <= bound:
            return x, y, round(n, 1), round(e, 1), round(rng.uniform(*alt), 1)
    raise SystemExit('havada_sec: sinir icinde hedef bulunamadi')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tohum', type=int, default=None)
    ap.add_argument('--baslangic', default='', help='X,Y: spawn here instead of a random spawn from --csv')
    ap.add_argument('--csv', default=os.path.expanduser('~/eland_veri/airsim_nh_baslangiclar.csv'))
    ap.add_argument('--yaricap', type=float, default=50.0)
    ap.add_argument('--irtifa', default='20,30')
    ap.add_argument('--sinir', type=float, default=370.0)
    ap.add_argument('--n', type=int, default=0)
    ap.add_argument('--cikti', default='')
    a = ap.parse_args()
    rng = random.Random(a.tohum)
    pts = [tuple(float(v) for v in a.baslangic.split(',')[:2])] if a.baslangic else spawns(a.csv)
    alt = tuple(float(v) for v in a.irtifa.split(','))
    if a.n:
        with open(a.cikti, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['x_ned', 'y_ned', 'hedef_n', 'hedef_e', 'irtifa'])
            for _ in range(a.n):
                w.writerow(draw(rng, pts, a.yaricap, alt, a.sinir))
        print(f'{a.n} havada baslangic -> {a.cikti} (tohum {a.tohum})')
        return
    x, y, n, e, h = draw(rng, pts, a.yaricap, alt, a.sinir)
    print(f'{x},{y} {n},{e},{h}')


if __name__ == '__main__':
    main()
