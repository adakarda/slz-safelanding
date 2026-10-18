"""M0 pilotu: AirSim kamera kipinde tepeden RGB ve SORA sinif haritasi (WSL'den, ~/airsim-venv ile).

    ~/airsim-venv/bin/python yakala.py --out DIR [--n 40] [--yukseklik 20 25 30 100] [--alan 150]

Nesne adlari objects.txt'ye, kurallara uyanlar sinif_eslesme.csv'ye yazilir. Sinif haritasi tek
segmentasyon goruntusunden cozulur (eland_airsim.siniflar: ID = sinif + 1, AirSim paleti).
Kanal sirasi (BGR/RGB) ilk karede iki yolla denenir ve hangisinin palet renklerini buldugu yazilir.
"""
import argparse
import csv
import math
import os

import sys

import airsim
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
try:  # WSL: the package; Windows: a copy of siniflar.py next to this file
    from eland_airsim import siniflar
except ImportError:
    sys.path.insert(0, HERE)
    import siniflar
try:
    import cv2

    def yaz(path, arr):
        cv2.imwrite(path, arr)
except ImportError:  # Windows venv: no OpenCV, PIL writes the same PNG
    from PIL import Image

    def yaz(path, arr):
        Image.fromarray(arr[..., ::-1] if arr.ndim == 3 else arr).save(path)


def poz(x, y, h, yaw):
    return airsim.Pose(airsim.Vector3r(x, y, -h), airsim.to_quaternion(0.0, 0.0, yaw))


def goruntu(client, tip):
    r = client.simGetImages([airsim.ImageRequest('0', tip, False, False)])[0]
    return np.frombuffer(r.image_data_uint8, np.uint8).reshape(r.height, r.width, 3)


def derinlik(client):
    r = client.simGetImages([airsim.ImageRequest('0', airsim.ImageType.DepthPlanar, True, False)])[0]
    return np.asarray(r.image_data_float, np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=40, help='yukseklik basina konum')
    ap.add_argument('--yukseklik', type=float, nargs='+', default=[20.0, 25.0, 30.0, 100.0])
    ap.add_argument('--alan', type=float, default=150.0, help='baslangic cevresinde +- metre')
    ap.add_argument('--tohum', type=int, default=0)
    ap.add_argument('--host', default='', help='bos: Windows uzerinde 127.0.0.1, WSL uzerinde Windows adresi')
    ap.add_argument('--tani', action='store_true', help='yollar ayri etiket (_gt8.png, v3 ham siniflari)')
    ap.add_argument('--derinlik-esik', type=float, default=2.0,
                    help='karedeki %%10 derinlik bundan kisaysa (m) konum yeniden cekilir; 0 = kapali')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    host = a.host or ('127.0.0.1' if os.name == 'nt' else __import__('eland_airsim.istemci').istemci.windows_host())
    client = airsim.VehicleClient(ip=host, timeout_value=60)
    client.confirmConnection()
    adlar = client.simListSceneObjects('.*')
    open(os.path.join(a.out, 'objects.txt'), 'w', encoding='utf-8').write('\n'.join(sorted(adlar)))
    esl = siniflar.classify_names(adlar)
    with open(os.path.join(a.out, 'sinif_eslesme.csv'), 'w', newline='') as f:
        csv.writer(f).writerows([('nesne', 'sinif')] + sorted(esl.items()))
    print(f'{len(adlar)} nesne, {len(esl)} tanesi bir sinifa eslesti', flush=True)
    print('atama:', siniflar.assign_ids(client), flush=True)
    if a.tani:  # roads on their own ID (8), signs back to structure; v3's raw 8th class is road
        yol = '.*(' + '|'.join(siniflar.ci(w) for w in ('road', 'street', 'asphalt', 'parking')) + ').*'
        print('tani: yol ayri', client.simSetSegmentationObjectID(yol, 8, True),
              client.simSetSegmentationObjectID('.*' + siniflar.ci('sign') + '.*', 4, True), flush=True)
    yerel = os.path.join(HERE, 'seg_rgbs.txt')
    pal = siniflar.palette(yerel if os.path.exists(yerel) else None)
    client.simSetCameraPose('0', airsim.Pose(airsim.Vector3r(0, 0, 0), airsim.to_quaternion(-math.pi / 2, 0, 0)))
    rng = np.random.default_rng(a.tohum)
    pozlar = [(float(x), float(y), h, float(rng.uniform(0, 2 * math.pi)))
              for h in a.yukseklik for x, y in rng.uniform(-a.alan, a.alan, (a.n, 2))]
    sira = None
    reddedilen = 0
    with open(os.path.join(a.out, 'kareler.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['i', 'x', 'y', 'h', 'yaw'])
        for i, (x, y, h, yaw) in enumerate(pozlar):
            for _ in range(30):  # a camera inside a building or on a roof edge sees almost nothing: draw again
                client.simSetVehiclePose(poz(x, y, h, yaw), True)
                if a.derinlik_esik <= 0 or np.percentile(derinlik(client), 10) >= a.derinlik_esik:
                    break
                reddedilen += 1
                x, y = (float(v) for v in rng.uniform(-a.alan, a.alan, 2))
            rgb = goruntu(client, airsim.ImageType.Scene)
            seg = goruntu(client, airsim.ImageType.Segmentation)
            if i == 0:  # the first frame after the ID change comes back unpainted (pilot 1: 100 % unknown)
                import time
                time.sleep(2.0)
                rgb = goruntu(client, airsim.ImageType.Scene)
                seg = goruntu(client, airsim.ImageType.Segmentation)
            if sira is None:
                bulunan = {o: int((siniflar.decode(seg, pal, o) > 0).sum()) for o in ('bgr', 'rgb')}
                if max(bulunan.values()) > 0:
                    sira = max(bulunan, key=bulunan.get)
                print(f'kanal sirasi: {sira} (palet rengi bulunan piksel {bulunan})', flush=True)
            cls = siniflar.labels_to_classes(siniflar.decode(seg, pal, sira or 'bgr'))
            bgr = rgb if (sira or 'bgr') == 'bgr' else rgb[..., ::-1]
            yaz(os.path.join(a.out, f'{i:04d}_rgb.png'), bgr)
            if a.tani:  # _gt8: v3's raw classes (7 = road, 255 = unknown); _gt keeps road as terrain-hazard
                img = seg[..., ::-1] if (sira or 'bgr') == 'bgr' else seg
                yolm = np.all(img == pal[8], axis=-1)
                gt8 = np.where(cls == 7, 255, cls).astype(np.uint8)
                gt8[yolm] = 7
                cls[yolm] = 2
                yaz(os.path.join(a.out, f'{i:04d}_gt8.png'), gt8)
            yaz(os.path.join(a.out, f'{i:04d}_gt.png'), cls)
            w.writerow([i, *[round(v, 3) for v in (x, y, h, yaw)]])
            if i % 20 == 0:
                print(f'{i}/{len(pozlar)} h {h:.0f} m, bilinmeyen pay %{100 * (cls == 7).mean():.1f}', flush=True)
    print(f'{len(pozlar)} kare: {a.out}; derinlik kontroluyle yeniden cekilen konum {reddedilen}')


if __name__ == '__main__':
    main()
