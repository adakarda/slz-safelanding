"""Dogma havuzu (Arda 28.10: rastgele dogma yerinde dron zeminin icinde dogup asagi dustu): aday noktalarda zeminin
PlayerStart seviyesine gore yuksekligini AirSim'den olcer (simTestLineOfSightBetweenPoints ile noktanin tam ustunden
asagi ikili arama). AirSim acik olmali (run_airsim.sh --yalniz-px4).

    ~/airsim-venv/bin/python zemin_olc.py WINDOWS_IP [--n 150]
Cikti: ~/rl_inis/senaryo/dogma_havuzu.csv (x_ned, y_ned, zemin_m: PlayerStart seviyesinin ustu, +yukari),
once bilinen 10 noktanin olcumu (dogrulama).
"""
import argparse
import math
import os
import random
import sys

import airsim
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from senaryo_uret import BILINEN, R_MERKEZ, Harita  # noqa: E402

LAT0, LON0, ALT0 = 47.641468, -122.140165, 122.0    # AirSim's default OriginGeopoint (settings set none)


def geo(n, e, yukari):
    r = 6378137.0
    g = airsim.GeoPoint()
    g.latitude = LAT0 + math.degrees(n / r)
    g.longitude = LON0 + math.degrees(e / (r * math.cos(math.radians(LAT0))))
    g.altitude = ALT0 + yukari
    return g


def zemin(c, n, e, ust=60.0, alt=-40.0):
    """Highest height (m above PlayerStart) from which the vertical line from `ust` is blocked; None if never."""
    if c.simTestLineOfSightBetweenPoints(geo(n, e, ust), geo(n, e, alt)):
        return None
    lo, hi = alt, ust                      # lo: blocked, hi: clear
    for _ in range(14):
        m = (lo + hi) / 2
        if c.simTestLineOfSightBetweenPoints(geo(n, e, ust), geo(n, e, m)):
            hi = m
        else:
            lo = m
    return round(hi, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ip')
    ap.add_argument('--n', type=int, default=150)
    a = ap.parse_args()
    c = airsim.MultirotorClient(ip=a.ip, timeout_value=20)
    c.confirmConnection()
    print('bilinen noktalar (dogrulama):')
    for l in open(BILINEN).read().split('\n')[1:]:
        if l.strip():
            x, y = map(float, l.split(',')[:2])
            print(f'  ({x:7.1f}, {y:7.1f}) zemin {zemin(c, x, y)} m')
    h = Harita()
    import cv2
    acik = (h.mesafe() >= 4.0).astype(np.uint8)
    lab = cv2.connectedComponents(acik)[1]
    rr, cc = np.nonzero(acik)
    n, e = h.dunya(rr, cc)
    ok = n ** 2 + e ** 2 <= (R_MERKEZ - 20) ** 2
    rr, cc, n, e = rr[ok], cc[ok], n[ok], e[ok]
    alanlar = sorted(set(lab[rr, cc].tolist()))
    rng = random.Random(0)
    satir = []
    for k in range(a.n):
        sec = np.nonzero(lab[rr, cc] == alanlar[k % len(alanlar)])[0]
        i = rng.choice(sec.tolist())
        z = zemin(c, float(n[i]), float(e[i]))
        if z is not None:
            satir.append(f'{n[i]:.1f},{e[i]:.1f},{z:.2f}')
    out = os.path.expanduser('~/rl_inis/senaryo/dogma_havuzu.csv')
    open(out, 'w').write('x_ned,y_ned,zemin_m\n' + '\n'.join(satir) + '\n')
    zs = [float(s.split(',')[2]) for s in satir]
    print(f'{len(satir)} nokta -> {out}; zemin {min(zs):.2f} .. {max(zs):.2f} m (medyan {np.median(zs):.2f})')


if __name__ == '__main__':
    main()
