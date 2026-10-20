"""M0 pilotu, WSL tarafi (v3 venv): v3'u AirSim karelerinde DEGISTIRMEDEN calistir, SORA gercegiyle karsilastir.

    ~/v3_test/venv/bin/python v3_olc.py <kare klasoru> [--fov 99.7]

Yukseklik basina: piksel dogrulugu, mIoU (karede 1000+ pikseli olan siniflar), guvenli/degil ikili dogruluk,
karisiklik matrisi. Gorsel kontrol icin her yukseklikten 3 bindirme. Bilinmeyen (7) pikseller sayilmaz.
"""
import argparse
import collections
import csv
import math
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, '/home/arda/v3_test/model')
sys.path.insert(0, '/home/arda/v3_test')
import v3_model as M  # noqa: E402

RENK = np.array([[90, 170, 70], [170, 170, 170], [60, 60, 60], [60, 80, 200], [200, 120, 40],
                 [40, 200, 230], [200, 40, 200], [0, 0, 0]], np.uint8)   # BGR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('klasor')
    ap.add_argument('--fov', type=float, default=99.7)
    a = ap.parse_args()
    model = M.yukle('/home/arda/v3_test/model/best_v3.pth')
    kareler = list(csv.DictReader(open(os.path.join(a.klasor, 'kareler.csv'))))
    os.makedirs(os.path.join(a.klasor, 'bindirme'), exist_ok=True)
    top = collections.defaultdict(lambda: np.zeros((7, 7), np.int64))
    sayi = collections.Counter()
    for k in kareler:
        i, h = int(k['i']), float(k['h'])
        bgr = cv2.imread(os.path.join(a.klasor, f'{i:04d}_rgb.png'))
        gt = cv2.imread(os.path.join(a.klasor, f'{i:04d}_gt.png'), cv2.IMREAD_UNCHANGED)
        gsd = 2 * h * math.tan(math.radians(a.fov) / 2) / bgr.shape[1] * 100
        pred = M.segmentle(model, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), gsd_cm=gsd)
        ok = (gt < 7) & (pred < 7)
        top[h] += np.bincount(gt[ok] * 7 + pred[ok], minlength=49).reshape(7, 7)
        sayi[h] += 1
        if sayi[h] <= 3:
            ust = np.concatenate([bgr, cv2.addWeighted(bgr, 0.5, RENK[gt], 0.5, 0), cv2.addWeighted(bgr, 0.5, RENK[pred], 0.5, 0)], 1)
            cv2.imwrite(os.path.join(a.klasor, 'bindirme', f'h{h:.0f}_{i:04d}.jpg'), cv2.resize(ust, None, fx=0.5, fy=0.5))
    print('yukseklik  kare  GSD cm/px  piksel dog.  mIoU   guvenli/degil')
    for h in sorted(top):
        cm = top[h]
        n = cm.sum()
        iou = [cm[c, c] / max(cm[c].sum() + cm[:, c].sum() - cm[c, c], 1) for c in range(7) if cm[c].sum() > 1000 * sayi[h]]
        guv = cm[:2, :2].sum() + cm[2:, 2:].sum()
        gsd = 2 * h * math.tan(math.radians(a.fov) / 2) / 1920 * 100
        print(f'{h:8.0f} m  {sayi[h]:4d}  {gsd:8.1f}  {cm.trace() / n:10.3f}  {np.mean(iou):5.3f}  {guv / n:10.3f}')
        print('   karisiklik (satir gercek, sutun v3; %; son sutun gercek pay %, IoU):')
        for c in range(7):
            if cm[c].sum():
                iou_c = cm[c, c] / max(cm[c].sum() + cm[:, c].sum() - cm[c, c], 1)
                print('   ', c, ' '.join(f'{100 * v / cm[c].sum():5.1f}' for v in cm[c]),
                      f' | {100 * cm[c].sum() / n:5.1f}  {iou_c:.3f}')
    # M0 gate (pre-registered): 20-30 m together, safe/not >= 0.85 and mIoU >= 0.55
    hs = [h for h in top if 20 <= h <= 30]
    cm = sum(top[h] for h in hs)
    n = cm.sum()
    iou = [cm[c, c] / max(cm[c].sum() + cm[:, c].sum() - cm[c, c], 1) for c in range(7)
           if cm[c].sum() > 1000 * sum(sayi[h] for h in hs)]
    guv = (cm[:2, :2].sum() + cm[2:, 2:].sum()) / n
    print(f'KAPI 20-30 m: guvenli/degil {guv:.3f} (>= 0.85), mIoU {np.mean(iou):.3f} (>= 0.55) -> '
          f'{"GECTI" if guv >= 0.85 and np.mean(iou) >= 0.55 else "KALDI"}')


if __name__ == '__main__':
    main()
