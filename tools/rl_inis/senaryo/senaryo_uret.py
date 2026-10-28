"""AirSim acil inis senaryosu, uretec (docs/airsim/SENARYO_PLANI.md, Arda 28.10). ROS'suz.

Her cagrida: rastgele dogma yeri (merkez dairede, inilebilir zemin, yapi/agactan >= 5 m), 3-6 noktali ozgun rota
(30 m, bacak 40-120 m, donus <= 135 deg, hepsi merkezde) ve rotanin %35-%65'i arasinda bir acil inis noktasi.
Koordinatlar PlayerStart'a gore NED metre (kuzey, dogu). Gecmis rotalar senaryo_gecmisi.jsonl'da; ayni ozet tekrar
cekilmez.

    python3 senaryo_uret.py --cikti senaryo.json [--tohum N] [--onizleme onizleme.png] [--bilinen]
"""
import argparse
import hashlib
import json
import math
import os
import random
import time

import cv2
import numpy as np

HARITA = '/mnt/c/Users/arda_/airsim/orto_nh/harita.npz'
RGB = '/mnt/c/Users/arda_/airsim/orto_nh/harita_rgb.jpg'
BILINEN = os.path.expanduser('~/eland_veri/airsim_nh_baslangiclar.csv')
GECMIS = os.path.expanduser('~/rl_inis/senaryo/senaryo_gecmisi.jsonl')
R_MERKEZ, IRTIFA = 150.0, 30.0


class Harita:
    def __init__(self):
        d = np.load(HARITA)
        self.res, self.n_top, self.e_sol = float(d['res']), float(d['n_top']), float(d['e_sol'])
        self.uygun = d['uygun']
        self.sinif = d['sinif']
        self._mesafe = None

    def piksel(self, n, e):
        return int(round((self.n_top - n) / self.res)), int(round((e - self.e_sol) / self.res))

    def dunya(self, r, c):
        return self.n_top - r * self.res, self.e_sol + c * self.res

    def mesafe(self):
        """Distance (m) of every grass / hard-ground pixel to the nearest other class. The map's own `uygun` carries
        the landing rule's buffers and leaves only ~3 % of the dense centre (max clearance 4 m), too little to spawn."""
        if self._mesafe is None:
            zemin = np.isin(self.sinif, (0, 1)).astype(np.uint8)
            self._mesafe = cv2.distanceTransform(zemin, cv2.DIST_L2, 5) * self.res
        return self._mesafe


def dogma_sec(h, rng, bilinen):
    if bilinen:
        rows = [l.split(',') for l in open(BILINEN).read().split('\n')[1:] if l.strip()]
        x, y = map(float, rng.choice(rows)[:2])
        return x, y, 'bilinen'
    # an open area first (each equally likely), then a point in it: drawing pixels directly kept landing in the one
    # big meadow (three draws within 2 m of each other, 28.10)
    acik = (h.mesafe() >= 4.0).astype(np.uint8)
    lab = cv2.connectedComponents(acik)[1]
    rr, cc = np.nonzero(acik)
    n, e = h.dunya(rr, cc)
    ok = n ** 2 + e ** 2 <= (R_MERKEZ - 20) ** 2
    rr, cc, n, e = rr[ok], cc[ok], n[ok], e[ok]
    alanlar = sorted(set(lab[rr, cc].tolist()))
    sec = lab[rr, cc] == rng.choice(alanlar)
    i = rng.randrange(int(sec.sum()))
    return round(float(n[sec][i]), 1), round(float(e[sec][i]), 1), 'rastgele'


def rota_cek(rng, bas):
    for _ in range(2000):
        k = rng.randint(3, 6)
        noktalar, yon = [bas], rng.uniform(0, 2 * math.pi)
        for _ in range(k):
            for _ in range(50):
                d = rng.uniform(40, 120)
                y2 = yon + rng.uniform(-math.radians(135), math.radians(135))
                p = (noktalar[-1][0] + d * math.cos(y2), noktalar[-1][1] + d * math.sin(y2))
                if p[0] ** 2 + p[1] ** 2 <= R_MERKEZ ** 2:
                    noktalar.append(p)
                    yon = y2
                    break
            else:
                break
        if len(noktalar) == k + 1:
            return [(round(n, 1), round(e, 1)) for n, e in noktalar[1:]]
    raise SystemExit('rota uretilemedi')


def ozet(rota):
    return hashlib.sha1(json.dumps([(round(n, -1), round(e, -1)) for n, e in rota]).encode()).hexdigest()[:12]


def acil_nokta(rng, bas, rota):
    yol = [bas] + rota
    uz = [math.dist(a, b) for a, b in zip(yol, yol[1:])]
    top = sum(uz)
    for _ in range(200):
        s = rng.uniform(0.35, 0.65) * top
        kalan, i = s, 0
        while kalan > uz[i]:
            kalan -= uz[i]
            i += 1
        if 15 < kalan < uz[i] - 15:             # on a straight leg, away from a turn
            a, b = yol[i], yol[i + 1]
            f = kalan / uz[i]
            return round(s, 1), (round(a[0] + f * (b[0] - a[0]), 1), round(a[1] + f * (b[1] - a[1]), 1)), i
    s = 0.5 * top
    return round(s, 1), yol[1], 0


def rgb_harita(h):
    """The ortho RGB at the class map's grid (0.2 m/px), stitched from the 200 m tiles (north up, east right;
    checked against the class tiles: 100 % agreement). Cached next to this script."""
    on = os.path.expanduser('~/rl_inis/senaryo/orto_rgb_0p2.jpg')
    if os.path.exists(on):
        return cv2.imread(on)
    D = os.path.dirname(HARITA)
    img = np.zeros(h.sinif.shape + (3,), np.uint8)
    for l in open(f'{D}/karolar.csv').read().split('\n')[1:]:
        if not l.strip():
            continue
        x, y, ad = l.split(',')
        t = cv2.imread(f'{D}/{ad}_rgb.png')
        r0, c0 = h.piksel(float(x) + 100, float(y) - 100)
        img[r0:r0 + 1000, c0:c0 + 1000] = cv2.resize(t, (1000, 1000), interpolation=cv2.INTER_AREA)
    cv2.imwrite(on, img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return img


def onizleme(h, sen, yol):
    img = rgb_harita(h)
    r0, c0 = h.piksel(R_MERKEZ + 20, -R_MERKEZ - 20)
    r1, c1 = h.piksel(-R_MERKEZ - 20, R_MERKEZ + 20)
    kes = img[r0:r1, c0:c1].copy()
    p = lambda n, e: (h.piksel(n, e)[1] - c0, h.piksel(n, e)[0] - r0)  # noqa: E731
    cv2.circle(kes, p(0, 0), int(R_MERKEZ / h.res), (255, 255, 255), 2)
    pts = [p(*q) for q in [sen['dogma']] + sen['rota']]
    cv2.polylines(kes, [np.array(pts, np.int32)], False, (0, 220, 255), 6, cv2.LINE_AA)
    for i, q in enumerate(pts):
        cv2.circle(kes, q, 14, (0, 0, 0) if i else (255, 120, 0), -1)
        cv2.putText(kes, str(i) if i else 'D', (q[0] - 9, q[1] + 9), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    a = p(*sen['acil_nokta'])
    cv2.drawMarker(kes, a, (0, 0, 255), cv2.MARKER_TILTED_CROSS, 40, 6)
    cv2.imwrite(yol, cv2.resize(kes, (900, 900), interpolation=cv2.INTER_AREA))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cikti', required=True)
    ap.add_argument('--tohum', type=int, default=None)
    ap.add_argument('--onizleme', default='')
    ap.add_argument('--bilinen', action='store_true', help='spawn from the 10 known clear points')
    a = ap.parse_args()
    tohum = a.tohum if a.tohum is not None else int(time.time() * 1000) % 2 ** 31
    rng = random.Random(tohum)
    h = Harita()
    gecmis = {json.loads(l)['ozet'] for l in open(GECMIS)} if os.path.exists(GECMIS) else set()
    x, y, tur = dogma_sec(h, rng, a.bilinen)
    for _ in range(100):
        rota = rota_cek(rng, (x, y))
        if ozet(rota) not in gecmis:
            break
    s, an, bacak = acil_nokta(rng, (x, y), rota)
    sen = dict(tohum=tohum, dogma=[x, y], dogma_turu=tur, irtifa=IRTIFA, r_merkez=R_MERKEZ,
               rota=[list(q) for q in rota], acil_mesafe_m=s, acil_nokta=list(an), acil_bacak=bacak,
               ozet=ozet(rota), zaman=time.strftime('%Y-%m-%d %H:%M:%S'))
    json.dump(sen, open(a.cikti, 'w'), indent=1)
    os.makedirs(os.path.dirname(GECMIS), exist_ok=True)
    with open(GECMIS, 'a') as f:
        f.write(json.dumps({'ozet': sen['ozet'], 'tohum': tohum, 'zaman': sen['zaman']}) + '\n')
    if a.onizleme:
        onizleme(h, sen, a.onizleme)
    yol_m = sum(math.dist(p, q) for p, q in zip([(x, y)] + rota, rota))
    print(f'senaryo {sen["ozet"]} (tohum {tohum}): dogma ({x}, {y}) {tur}, {len(rota)} nokta, rota {yol_m:.0f} m, '
          f'acil inis {s:.0f}. m ({an[0]}, {an[1]})')


if __name__ == '__main__':
    main()
