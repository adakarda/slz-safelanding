"""Duzeltme 29: v4 dogrulama sahneleri icin segmentasyon modellerinin (v3, v4) maskeleri. Modeller degismez; Arda'nin
yukleyicisi ve segmentle() aynen kullanilir. Sahadaki kamerayi taklit etmek icin fotograf once 9 cm/piksele
indirilir (640x480 kamera 20-30 m'de ~7-11 cm/px), sonra segmentle(gsd_cm=9). Cikti simulator siniflari (yol ->
terrain-hazard), sahne maskesi boyunda; liste val_<model>.txt satirlari "maske sx sy pred:... elev:...".

    ~/v3_test/venv/bin/python seg_maske.py
"""
import csv
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, '/home/arda/v3_test/model')
import v3_model as M  # noqa: E402

V = os.path.expanduser('~/eland_veri/v4_zip/veri_v4')
O = os.path.expanduser('~/eland_veri/rl/v4')
MODELLER = {'v3': '/home/arda/v3_test/model/best_v3.pth', 'v4': '/home/arda/v4_seg/best_v4.pth'}
KAMERA_GSD = 9.0


def main():
    man = {m['id'].replace('/', '__'): m for m in csv.DictReader(open(f'{V}/manifest.csv'))}
    satir = [l.split() for l in open(f'{O}/val.txt')]
    for ad, yol in MODELLER.items():
        model = M.yukle(yol)
        out = []
        for s in satir:
            isim = os.path.basename(s[0])[:-4]
            pp = f'{O}/pred_{ad}/val/{isim}.png'
            if not os.path.exists(pp):
                m = man[isim]
                bgr = cv2.imread(f"{V}/{m['goruntu']}")
                k = float(m['gsd_cm']) / KAMERA_GSD
                bgr = cv2.resize(bgr, (round(bgr.shape[1] * k), round(bgr.shape[0] * k)), interpolation=cv2.INTER_AREA)
                p = M.segmentle(model, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), gsd_cm=KAMERA_GSD)
                mh, mw = cv2.imread(s[0], cv2.IMREAD_UNCHANGED).shape[:2]
                os.makedirs(os.path.dirname(pp), exist_ok=True)
                cv2.imwrite(pp, cv2.resize(p, (mw, mh), interpolation=cv2.INTER_NEAREST))
            out.append(f'{s[0]} {s[1]} {s[2]} pred:{pp} {s[3]}\n')
        open(f'{O}/val_{ad}.txt', 'w').writelines(out)
        # pixel agreement with the ground truth, and how often an unsafe pixel is called safe
        uy, ys, n = 0, 0, 0
        for s in satir:
            g = cv2.imread(s[0], cv2.IMREAD_UNCHANGED)
            p = cv2.imread(f'{O}/pred_{ad}/val/{os.path.basename(s[0])}', cv2.IMREAD_UNCHANGED)
            ok = g < 7
            uy += int((g[ok] == p[ok]).sum())
            n += int(ok.sum())
            tehlike = ok & (g >= 2)
            ys += int((tehlike & (p <= 1)).sum()) / max(int(tehlike.sum()), 1)
        print(f'{ad}: piksel uyumu %{100 * uy / n:.1f}, tehlikeliyi guvenli sanma (kare ort.) %{100 * ys / len(satir):.1f}',
              flush=True)


if __name__ == '__main__':
    main()
