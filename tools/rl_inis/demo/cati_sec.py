"""Roof air starts for the AirSim demo (Arda, 19.10: "binalarin catilarinin ustunde test etmek istiyorum").

    ~/v3_test/venv/bin/python cati_sec.py [--n 6] [--irtifa 25] [--cikti cati.csv] [--png cati.png]

Houses are the big class-3 (yapi) blobs of the AirSimNH ortho map (orto_nh/harita.npz, 0.2 m): opened with
a 1.6 m kernel so fences, poles and wires drop out, then kept if >= 60 m2. Each roof's target is its most
interior point (distance-transform max), so the vehicle starts straight over the roof, not over its edge.
A roof is paired with the nearest known clear spawn (airsim_nh_baslangiclar.csv, the Faz 3 starts) 20..90 m
away; the list spreads over the spawns (at most 2 roofs per spawn) and is sorted by spawn.
Output: x_ned,y_ned,hedef_n,hedef_e,irtifa (inis_sina.sh / run_airsim.sh --baslangic X,Y --havada N,E,ALT)
plus columns for the report: roof area, roof half-width, distance to the nearest landable (uygun) cell.
"""
import argparse
import csv
import math
import os

import cv2
import numpy as np

H = os.path.expanduser('~')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--harita', default='/mnt/c/Users/arda_/airsim/orto_nh/harita.npz')
    ap.add_argument('--spawn', default=f'{H}/eland_veri/airsim_nh_baslangiclar.csv')
    ap.add_argument('--n', type=int, default=6)
    ap.add_argument('--irtifa', type=float, default=25.0)
    ap.add_argument('--cikti', default=f'{H}/rl_inis/demo/cati.csv')
    ap.add_argument('--png', default='')
    a = ap.parse_args()

    h = np.load(a.harita)
    m, res, n_top, e_sol = h['sinif'], float(h['res']), float(h['n_top']), float(h['e_sol'])
    uygun = h['uygun']
    yapi = (m == 3).astype(np.uint8)
    k = int(round(1.6 / res))
    yapi = cv2.morphologyEx(yapi, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    n_c, lab, st, _ = cv2.connectedComponentsWithStats(yapi, connectivity=8)
    ic = cv2.distanceTransform(yapi, cv2.DIST_L2, 5) * res
    d_uygun = cv2.distanceTransform((~uygun).astype(np.uint8), cv2.DIST_L2, 5) * res
    spawns = [(float(r['x_ned']), float(r['y_ned'])) for r in csv.DictReader(open(a.spawn))]

    catilar = []
    for c in range(1, n_c):
        alan = st[c, cv2.CC_STAT_AREA] * res * res
        if alan < 60:
            continue
        x, y, w, hh = (st[c, i] for i in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP, cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        parca = np.where(lab[y:y + hh, x:x + w] == c, ic[y:y + hh, x:x + w], 0)
        i, j = np.unravel_index(np.argmax(parca), parca.shape)
        i, j = i + y, j + x
        n, e = n_top - i * res, e_sol + j * res
        if max(abs(n), abs(e)) > 360:
            continue
        uz = [(math.hypot(n - sx, e - sy), sx, sy) for sx, sy in spawns]
        uz = [u for u in uz if 20 <= u[0] <= 90]
        if not uz:
            continue
        d, sx, sy = min(uz)
        catilar.append(dict(n=n, e=e, alan=alan, yari=float(ic[i, j]), uygun_m=float(d_uygun[i, j]),
                            sx=sx, sy=sy, d=d))

    # spread over spawns: round-robin, the biggest roof of each spawn first
    gruplar = {}
    for c in sorted(catilar, key=lambda c: -c['alan']):
        gruplar.setdefault((c['sx'], c['sy']), []).append(c)
    secim = []
    for tur in range(2):
        for g in gruplar.values():
            if len(g) > tur and len(secim) < a.n:
                secim.append(g[tur])
    with open(a.cikti, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['x_ned', 'y_ned', 'hedef_n', 'hedef_e', 'irtifa', 'cati_alan_m2', 'cati_yari_m', 'uygun_m'])
        for c in secim:
            w.writerow([c['sx'], c['sy'], round(c['n'] - c['sx'], 1), round(c['e'] - c['sy'], 1), a.irtifa,
                        round(c['alan']), round(c['yari'], 1), round(c['uygun_m'], 1)])
    print(f'{len(catilar)} cati aday (>= 60 m2, bir dogma noktasina 20-90 m); {len(secim)} secildi -> {a.cikti}')
    for c in secim:
        print(f"  cati NED ({c['n']:7.1f}, {c['e']:7.1f})  alan {c['alan']:4.0f} m2  ic yaricap {c['yari']:4.1f} m  "
              f"en yakin uygun {c['uygun_m']:4.1f} m  | dogma ({c['sx']}, {c['sy']}) {c['d']:4.0f} m")
    if a.png:
        renk = np.array([[70, 170, 90], [175, 175, 175], [40, 110, 40], [200, 80, 60], [40, 110, 200],
                         [230, 200, 40], [230, 40, 200], [90, 90, 90]], np.uint8)
        kucuk = cv2.resize(m, (800, 800), interpolation=cv2.INTER_NEAREST)
        img = np.full((800, 800, 3), 30, np.uint8)
        ok = kucuk < 8
        img[ok] = renk[kucuk[ok]]
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        px = lambda n, e: (int((e - e_sol) / 1.0), int((n_top - n) / 1.0))  # noqa: E731
        for sx, sy in spawns:
            cv2.circle(img, px(sx, sy), 5, (255, 255, 255), -1)
        for k_, c in enumerate(secim, 1):
            cv2.line(img, px(c['sx'], c['sy']), px(c['n'], c['e']), (255, 255, 255), 1)
            cv2.circle(img, px(c['n'], c['e']), 7, (0, 0, 255), 2)
            cv2.putText(img, str(k_), (px(c['n'], c['e'])[0] + 8, px(c['n'], c['e'])[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imwrite(a.png, img)


if __name__ == '__main__':
    main()
