"""Ortografik karolari birlestir, SORA uygunlugunu (detector_node kurallari) hesapla, baslangic noktasi sec.

    ~/v3_test/venv/bin/python orto_analiz.py DIR [--n 10] [--tohum 0]

Cikti (DIR icinde):
  harita.npz        sinif haritasi 0.2 m (0..6, 7 = yol, 255 = bilinmeyen), uygun hucreler, kose NED
  harita_gt.png     renkli etiket haritasi (1 m/piksel), uygun alanlar sari, baslangiclar beyaz
  harita_rgb.jpg    RGB mozaik (1 m/piksel)
  baslangiclar.csv  x_ned, y_ned, en yakin uygun hucre (m)
Uygunluk (eland_params.yaml detector_node): guvenli {0,1}, tehlike {3,4,5,6}, r_fit 1.0, r_class_edge 2.0,
r_hazard 3.0, min_area 9 m2; yol (7) sinif kenari hesabinda terrain-hazard (2) sayilir.
Baslangic: yol hucresi, agac/yapi/su/aracdan >= 4 m (dikey kalkis temiz), 8-20 m icinde uygun hucre var;
birbirine >= 40 m (en uzak nokta ornekleme).
"""
import argparse
import csv
import os

import cv2
import numpy as np
from PIL import Image

RES0 = 0.1      # karo cozunurlugu (200 m / 2000 px)
RES = 0.2
RENK = np.array([[70, 170, 90], [175, 175, 175], [40, 110, 40], [200, 80, 60], [40, 110, 200],
                 [230, 200, 40], [200, 40, 200], [90, 90, 90]], np.uint8)   # RGB; 7 = yol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('klasor')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--tohum', type=int, default=0)
    a = ap.parse_args()
    karolar = list(csv.DictReader(open(os.path.join(a.klasor, 'karolar.csv'))))
    xs = sorted({float(k['x']) for k in karolar})
    ys = sorted({float(k['y']) for k in karolar})
    w = 200.0
    n_top, e_sol = max(xs) + w / 2, min(ys) - w / 2
    H = round((max(xs) - min(xs) + w) / RES0)
    W = round((max(ys) - min(ys) + w) / RES0)
    gt = np.full((H, W), 255, np.uint8)
    rgb = np.zeros((H // 10, W // 10, 3), np.uint8)
    for k in karolar:
        x, y = float(k['x']), float(k['y'])
        r0, c0 = round((n_top - (x + w / 2)) / RES0), round(((y - w / 2) - e_sol) / RES0)
        g = np.array(Image.open(os.path.join(a.klasor, k['dosya'] + '_gt8.png')))
        gt[r0:r0 + g.shape[0], c0:c0 + g.shape[1]] = g
        im = np.array(Image.open(os.path.join(a.klasor, k['dosya'] + '_rgb.png')).convert('RGB'))
        rgb[r0 // 10:(r0 + g.shape[0]) // 10, c0 // 10:(c0 + g.shape[1]) // 10] = cv2.resize(im, (g.shape[1] // 10, g.shape[0] // 10), interpolation=cv2.INTER_AREA)
    # seam check: labels just across a horizontal tile border should mostly agree
    sat = round(w / RES0)
    ayni = [np.mean(gt[r - 1, :] == gt[r, :]) for r in range(sat, H, sat)]
    print('karo dikis uyumu (yatay sinirlar, ayni etiket orani):', [round(float(v), 3) for v in ayni])

    s = 2
    m = gt[::s, ::s]
    sinif = np.where(m == 7, 2, np.where(m == 255, 7, m)).astype(np.uint8)   # road counts as terrain-hazard
    safe = np.isin(sinif, [0, 1]).astype(np.uint8)
    hazard = np.isin(sinif, [3, 4, 5, 6]).astype(np.uint8)
    d_fit = cv2.distanceTransform(safe, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * RES
    edge = np.zeros(sinif.shape, np.uint8)
    edge[:, :-1] |= sinif[:, :-1] != sinif[:, 1:]
    edge[:, 1:] |= sinif[:, 1:] != sinif[:, :-1]
    edge[:-1, :] |= sinif[:-1, :] != sinif[1:, :]
    edge[1:, :] |= sinif[1:, :] != sinif[:-1, :]
    d_edge = cv2.distanceTransform(1 - edge, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * RES
    d_haz = cv2.distanceTransform(1 - hazard, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * RES
    n_lab, lab, st, _ = cv2.connectedComponentsWithStats(safe, connectivity=8)
    big = st[:, cv2.CC_STAT_AREA] * RES * RES >= 9.0
    big[0] = False
    uygun = big[lab] & (d_fit >= 1.0) & (d_edge >= 2.0) & (d_haz >= 3.0)
    print(f'uygun alan {uygun.sum() * RES * RES:.0f} m2 / {uygun.size * RES * RES:.0f} m2; '
          f'sinif paylari %: ' + ' '.join(f'{c}:{100 * np.mean(m == c):.1f}' for c in [0, 1, 2, 3, 4, 5, 6, 7, 255]))

    # takeoff points: road, >= 4 m from trees/structures/water/vehicles, an eligible cell 8..20 m away
    engel = np.isin(m, [2, 3, 4, 5, 255]).astype(np.uint8)
    d_engel = cv2.distanceTransform(1 - engel, cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * RES
    d_uygun = cv2.distanceTransform(1 - uygun.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * RES
    aday = (m == 7) & (d_engel >= 4.0) & (d_uygun >= 8.0) & (d_uygun <= 20.0)
    rr, cc = np.nonzero(aday)
    print(f'aday baslangic hucresi {len(rr)}')
    rng = np.random.default_rng(a.tohum)
    secilen = []
    if len(rr):
        i = int(rng.integers(len(rr)))
        secilen.append(i)
        dmin = np.hypot(rr - rr[i], cc - cc[i]) * RES
        while len(secilen) < a.n:
            j = int(np.argmax(dmin))
            if dmin[j] < 40.0:
                break
            secilen.append(j)
            dmin = np.minimum(dmin, np.hypot(rr - rr[j], cc - cc[j]) * RES)
    nokta = [(n_top - (rr[i] + 0.5) * RES, e_sol + (cc[i] + 0.5) * RES, float(d_uygun[rr[i], cc[i]])) for i in secilen]
    with open(os.path.join(a.klasor, 'baslangiclar.csv'), 'w', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['x_ned', 'y_ned', 'uygun_uzaklik_m'])
        for x, y, d in nokta:
            wr.writerow([round(x, 1), round(y, 1), round(d, 1)])
            print(f'baslangic NED ({x:7.1f}, {y:7.1f}), en yakin uygun hucre {d:.1f} m')
    np.savez_compressed(os.path.join(a.klasor, 'harita.npz'), sinif=m, uygun=uygun, res=RES,
                        n_top=n_top, e_sol=e_sol)
    k = 5   # 0.2 m -> 1 m
    goster = RENK[np.where(m[::k, ::k] == 255, 7, m[::k, ::k])].copy()
    goster[m[::k, ::k] == 255] = [0, 0, 0]
    goster[uygun[::k, ::k]] = [255, 230, 0]
    for x, y, _ in nokta:
        r, c = int((n_top - x) / (RES * k)), int((y - e_sol) / (RES * k))
        cv2.circle(goster, (c, r), 6, (255, 255, 255), 2)
    Image.fromarray(goster).save(os.path.join(a.klasor, 'harita_gt.png'))
    Image.fromarray(rgb).save(os.path.join(a.klasor, 'harita_rgb.jpg'), quality=85)


if __name__ == '__main__':
    main()
