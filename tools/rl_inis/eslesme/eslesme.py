"""F1 match test, part 2: Gazebo's rendered class map against the environment's projection.

Runs beside a flight in the orto_dji0097_sinif world. Every `aralik_s` of sim
time it takes the RGB camera frame, reads the class back from the hue, and
renders the same view with eland_rl's Camera at the vehicle pose that has the
nearest sim timestamp. Scores: pixel agreement, mIoU and frequency-weighted
IoU, over all pixels and over interior pixels (more than 2 px from a class
edge, where texture filtering cannot blur the answer).

    python3 eslesme.py <cikti_klasoru> <sure_s>
"""
import math
import os
import sys
import threading
import time

import cv2
import numpy as np
from gz.msgs10.image_pb2 import Image as GzImage
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node as GzNode

from eland_rl.camera import Camera
from eland_rl.scene import Scene

sys.path.insert(0, os.path.dirname(__file__))
from sinif_dunyasi import TON  # noqa: E402

DUNYA, MODEL = 'orto_dji0097_sinif', 'x500_seg_cam_rgb_down_0'
OFSET, ZEMIN = 0.10, 0.02
N = 8


def oku_sinif(rgb):
    """Class from hue; low saturation or dark -> 7."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV_FULL).astype(np.float32)
    ton = hsv[..., 0] * 360.0 / 256.0
    out = np.full(rgb.shape[:2], 7, np.uint8)
    en_iyi = np.full(rgb.shape[:2], 1e9, np.float32)
    for k, t in TON.items():
        d = np.abs((ton - t + 180) % 360 - 180)
        sec = d < en_iyi
        out[sec], en_iyi[sec] = k, d[sec]
    out[(hsv[..., 1] < 128) | (hsv[..., 2] < 40) | (en_iyi > 15)] = 7
    return out


def rotasyon(q):
    x, y, z, s = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * s), 2 * (x * z + y * s)],
                     [2 * (x * y + z * s), 1 - 2 * (x * x + z * z), 2 * (y * z - x * s)],
                     [2 * (x * z - y * s), 2 * (y * z + x * s), 1 - 2 * (x * x + y * y)]])


def puan(cm):
    tp = np.diag(cm).astype(float)
    un = cm.sum(0) + cm.sum(1) - tp
    iou = np.where(un > 0, tp / np.maximum(un, 1), np.nan)
    frek = cm.sum(1) / max(cm.sum(), 1)
    return tp.sum() / max(cm.sum(), 1), np.nanmean(iou), np.nansum(frek * np.nan_to_num(iou)), iou


def main(cikti, sure_s, aralik_s=0.5):
    os.makedirs(cikti, exist_ok=True)
    H = os.path.expanduser('~')
    sahne = Scene.from_messi(f'{H}/v3_test/foto/fotoo/DJI_0097.JPG', f'{H}/v3_test/maske/fotomask/DJI_0097.png',
                             size_m=(64.02, 42.68), name='DJI_0097')
    pozlar, kilit = [], threading.Lock()
    kareler = []

    def on_poz(msg):
        t = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
        for ps in msg.pose:
            if ps.name == MODEL:
                with kilit:
                    pozlar.append((t, np.array([ps.position.x, ps.position.y, ps.position.z]),
                                   np.array([ps.orientation.x, ps.orientation.y, ps.orientation.z, ps.orientation.w])))
                    while pozlar and pozlar[0][0] < t - 30.0:
                        pozlar.pop(0)
                return

    son = {'t': -1e9}

    def on_kare(msg):
        t = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
        if t - son['t'] < aralik_s:
            return
        son['t'] = t
        img = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width, -1)[..., :3].copy()
        with kilit:
            kareler.append((t, img))

    gz = GzNode()
    if not gz.subscribe(Pose_V, f'/world/{DUNYA}/dynamic_pose/info', on_poz):
        sys.exit('poz konusu yok')
    if not gz.subscribe(GzImage, 'v3_rgb', on_kare):
        sys.exit('kamera konusu yok')
    cm_tum, cm_ic = np.zeros((N, N), np.int64), np.zeros((N, N), np.int64)
    satirlar = []
    sayac = {'yakalanan': 0, 'pozsuz': 0, 'yerde': 0}
    t0 = time.time()
    while time.time() - t0 < sure_s:
        time.sleep(1.0)
        son_tur = os.path.exists(f'{cikti}/DUR')
        with kilit:
            if not pozlar:
                continue
            pz = list(pozlar)
            hazir = [k for k in kareler if k[0] < pz[-1][0] - 0.5]
            kareler[:] = [k for k in kareler if k[0] >= pz[-1][0] - 0.5]
        pt = np.array([p[0] for p in pz])
        for t, img in hazir:
            n = sayac['yakalanan']
            sayac['yakalanan'] += 1
            j = int(np.argmin(np.abs(pt - t)))
            dt = pt[j] - t
            if abs(dt) > 0.03:
                sayac['pozsuz'] += 1
                continue
            _, p, q = pz[j]
            R = rotasyon(q)
            c = p + R @ np.array([0.0, 0.0, OFSET])
            c[2] -= ZEMIN
            if c[2] < 3.0:
                sayac['yerde'] += 1
                continue
            h, w = img.shape[:2]
            beklenen = Camera.label_image(sahne, c, R, w, h)
            gorulen = oku_sinif(img)
            kenar = cv2.dilate((cv2.Laplacian(beklenen.astype(np.float32), cv2.CV_32F) != 0).astype(np.uint8),
                               np.ones((5, 5), np.uint8)) > 0
            cm = np.bincount(beklenen.ravel() * N + gorulen.ravel(), minlength=N * N).reshape(N, N)
            ic = ~kenar
            cmi = np.bincount(beklenen[ic] * N + gorulen[ic], minlength=N * N).reshape(N, N)
            cm_tum += cm
            cm_ic += cmi
            egim = math.degrees(math.acos(max(-1.0, min(1.0, R[2, 2]))))
            a_t, _, _, _ = puan(cm)
            a_i, _, _, _ = puan(cmi)
            satirlar.append((t, c[2], egim, dt, a_t, a_i))
            if n % 20 == 0:
                from sinif_dunyasi import PALET
                yan = np.concatenate([img, PALET[gorulen], PALET[beklenen]], 1)
                cv2.imwrite(f'{cikti}/kare_{n:03d}.png', cv2.cvtColor(yan, cv2.COLOR_RGB2BGR))
        if son_tur:
            break
    np.savez(f'{cikti}/eslesme.npz', cm_tum=cm_tum, cm_ic=cm_ic, satirlar=np.array(satirlar))
    s = np.array(satirlar)
    if not len(s):
        sys.exit(f'eslesen kare yok: {sayac}')
    for ad, cm in (('tum pikseller', cm_tum), ('ic pikseller', cm_ic)):
        acc, miou, fwiou, iou = puan(cm)
        print(f'{ad}: piksel uyumu {acc:.4f}, mIoU {miou:.4f}, fwIoU {fwiou:.4f}, '
              f'sinif IoU {np.round(iou, 3).tolist()}')
    print(f'{len(s)} kare puanlandi {sayac}, yukseklik {s[:, 1].min():.1f}-{s[:, 1].max():.1f} m, '
          f'egim en cok {s[:, 2].max():.1f} deg, poz-kare zaman farki en cok {np.abs(s[:, 3]).max() * 1000:.0f} ms')
    for alt, ust in ((0, 2), (2, 5), (5, 90)):
        m = (s[:, 2] >= alt) & (s[:, 2] < ust)
        if m.any():
            print(f'  egim {alt}-{ust} deg: {m.sum()} kare, ic piksel uyumu ort {s[m, 5].mean():.4f} '
                  f'(en kotu {s[m, 5].min():.4f})')


if __name__ == '__main__':
    main(sys.argv[1], float(sys.argv[2]))
