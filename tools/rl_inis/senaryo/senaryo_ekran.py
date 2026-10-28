"""AirSim acil inis senaryosu, tek ekran (docs/airsim/SENARYO_PLANI.md): solda gorev haritasi, ortada AirSim'in
gimbal'li segmentasyon kamerasi (gercek etiket) ve bizim v4 segmentasyonumuz, sagda RL komutlari.

    source /opt/ros/jazzy/setup.bash; python3 senaryo_ekran.py
"""
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

RENK = np.array([(86, 140, 61), (148, 148, 140), (43, 102, 36), (173, 166, 153), (36, 87, 143), (200, 40, 40),
                 (240, 150, 30), (40, 40, 40)], np.uint8)[:, ::-1]          # eland_common.classes, RGB -> BGR
KONU = {'harita': '/eland/senaryo/harita', 'gt': '/camera/segmentation', 'v4': '/eland/v3/maske', 'rl': '/eland/rl/gorus'}
W, H = 1700, 920


def oku(m):
    a = np.frombuffer(m.data, np.uint8)
    if m.encoding in ('rgb8', 'bgr8'):
        a = a.reshape(m.height, m.step)[:, :m.width * 3].reshape(m.height, m.width, 3)
        return a[:, :, ::-1] if m.encoding == 'rgb8' else a
    if m.encoding == 'mono8':
        return a.reshape(m.height, m.step)[:, :m.width]
    return None


def sigdir(img, w, h):
    s = min(w / img.shape[1], h / img.shape[0])
    r = cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)), interpolation=cv2.INTER_NEAREST)
    out = np.full((h, w, 3), 18, np.uint8)
    y, x = (h - r.shape[0]) // 2, (w - r.shape[1]) // 2
    out[y:y + r.shape[0], x:x + r.shape[1]] = r
    return out


class Ekran(Node):
    def __init__(self):
        super().__init__('senaryo_ekran')
        self.son = {}
        for k, t in KONU.items():
            for qos in (qos_profile_sensor_data, 1):
                self.create_subscription(Image, t, lambda m, k=k: self.son.__setitem__(k, m), qos)
        self.kare = {k: None for k in KONU}


def baslik(img, yazi):
    cv2.rectangle(img, (0, 0), (img.shape[1], 30), (0, 0, 0), -1)
    cv2.putText(img, yazi, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def main():
    rclpy.init()
    n = Ekran()
    cv2.namedWindow('Acil inis senaryosu', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Acil inis senaryosu', W, H)
    cv2.moveWindow('Acil inis senaryosu', 0, 0)
    while rclpy.ok():
        rclpy.spin_once(n, timeout_sec=0.03)
        for k, m in list(n.son.items()):
            img = oku(m)
            if img is None:
                continue
            if k == 'gt':                       # class + 1, 0 = unknown
                img = RENK[np.where(img == 0, 7, np.clip(img.astype(int) - 1, 0, 7))]
            elif k == 'v4':
                img = RENK[np.clip(img, 0, 7)]
            n.kare[k] = img
        n.son.clear()
        ekran = np.full((H, W, 3), 12, np.uint8)
        bos = lambda w, h: np.full((h, w, 3), 30, np.uint8)  # noqa: E731
        hw = 900
        ekran[10:10 + hw, 10:10 + 860] = sigdir(n.kare['harita'] if n.kare['harita'] is not None else bos(860, hw), 860, hw)
        g = baslik(sigdir(n.kare['gt'] if n.kare['gt'] is not None else bos(480, 360), 480, 400),
                   'AirSim gimbal kamera: gercek segmentasyon')
        v = baslik(sigdir(n.kare['v4'] if n.kare['v4'] is not None else bos(480, 360), 480, 400),
                   'Bizim segmentasyon modelimiz (v4)')
        ekran[10:410, 880:1360] = g
        ekran[430:830, 880:1360] = v
        r = baslik(sigdir(n.kare['rl'] if n.kare['rl'] is not None else bos(320, 360), 320, 400), 'RL komutlari')
        ekran[10:410, 1370:1690] = r
        lej = ekran[430:830, 1370:1690]
        for i, ad in enumerate(['cim/toprak', 'sert zemin', 'bitki/yol', 'yapi', 'su', 'arac', 'insan', 'bilinmiyor']):
            cv2.rectangle(lej, (10, 20 + 34 * i), (36, 44 + 34 * i), RENK[i].tolist(), -1)
            cv2.putText(lej, ad, (46, 39 + 34 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.imshow('Acil inis senaryosu', ekran)
        if cv2.waitKey(15) == 27:
            break
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
