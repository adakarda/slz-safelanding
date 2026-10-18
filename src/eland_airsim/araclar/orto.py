"""Ortografik tepe haritasi: AirSim kamera kipinde karo karo RGB + SORA etiketi (yollar ayri, 8).

    python orto.py --out DIR [--merkez -300 -100 100 300] [--genislik 200] [--yukseklik 150]

settings_orto.json ile acilmis bir dunyada calisir (ProjectionMode orthographic, OrthoWidth = karo
genisligi). Yaw 0: goruntunun ustu kuzey (+x NED), sagi dogu (+y). Her karo DIR/karo_<x>_<y>_{rgb,gt8}.png;
gt8: 0..6 SORA sinifi, 7 = yol, 255 = bilinmeyen. karolar.csv: merkezler.
"""
import argparse
import csv
import math
import os
import sys
import time

import airsim
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import siniflar  # noqa: E402


def goruntu(client, tip):
    r = client.simGetImages([airsim.ImageRequest('0', tip, False, False)])[0]
    return np.frombuffer(r.image_data_uint8, np.uint8).reshape(r.height, r.width, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--merkez', type=float, nargs='+', default=[-300.0, -100.0, 100.0, 300.0])
    ap.add_argument('--yukseklik', type=float, default=150.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    c = airsim.VehicleClient(ip='127.0.0.1', timeout_value=60)
    c.confirmConnection()
    print('atama:', siniflar.assign_ids(c), flush=True)
    yol = '.*(' + '|'.join(siniflar.ci(w) for w in ('road', 'street', 'asphalt', 'parking')) + ').*'
    print('yol ayri:', c.simSetSegmentationObjectID(yol, 8, True),
          c.simSetSegmentationObjectID('.*' + siniflar.ci('sign') + '.*', 4, True), flush=True)
    pal = siniflar.palette(os.path.join(HERE, 'seg_rgbs.txt'))
    c.simSetCameraPose('0', airsim.Pose(airsim.Vector3r(0, 0, 0), airsim.to_quaternion(-math.pi / 2, 0, 0)))
    ilk = True
    with open(os.path.join(a.out, 'karolar.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['x', 'y', 'dosya'])
        for x in a.merkez:
            for y in a.merkez:
                c.simSetVehiclePose(airsim.Pose(airsim.Vector3r(x, y, -a.yukseklik), airsim.to_quaternion(0, 0, 0)), True)
                if ilk:
                    time.sleep(2.0)
                    goruntu(c, airsim.ImageType.Segmentation)
                    ilk = False
                time.sleep(0.5)
                rgb = goruntu(c, airsim.ImageType.Scene)          # BGR (pilot: bgr)
                seg = goruntu(c, airsim.ImageType.Segmentation)
                img = seg[..., ::-1]
                gt8 = np.where(siniflar.decode(seg, pal, 'bgr') == 0, 255,
                               siniflar.decode(seg, pal, 'bgr').astype(np.int16) - 1).astype(np.uint8)
                gt8[np.all(img == pal[8], axis=-1)] = 7
                ad = f'karo_{x:+.0f}_{y:+.0f}'
                Image.fromarray(rgb[..., ::-1]).save(os.path.join(a.out, ad + '_rgb.png'))
                Image.fromarray(gt8).save(os.path.join(a.out, ad + '_gt8.png'))
                w.writerow([x, y, ad])
                print(f'{ad}: bilinmeyen %{100 * (gt8 == 255).mean():.1f}, yol %{100 * (gt8 == 7).mean():.1f}',
                      flush=True)


if __name__ == '__main__':
    main()
