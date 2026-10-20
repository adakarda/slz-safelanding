"""Faz 3 duman testi: kamera, AirSim etiketi ve algi maskesinden birer kare kaydet (+ yan yana PNG).

    source /opt/ros/jazzy/setup.bash && source ~/ros2_ws/install/setup.bash
    PYTHONPATH=/usr/lib/python3/dist-packages:$PYTHONPATH python3 faz3_kare.py OUT_DIR
"""
import os
import sys
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

from eland_common import classes
from eland_common.qos import SENSOR_QOS

KONULAR = {'kamera': '/camera/image', 'gt': '/camera/segmentation', 'maske': '/eland/semantic_mask',
           'v3': '/eland/v3/etiket'}
RENK = np.array([classes.CLASS_COLORS[i] for i in range(8)], np.uint8)


def dizi(m):
    ch = 3 if m.encoding in ('rgb8', 'bgr8') else 1
    a = np.frombuffer(m.data, np.uint8).reshape(m.height, m.step)[:, :m.width * ch]
    return a.reshape(m.height, m.width, ch) if ch == 3 else a


class Kare(Node):
    def __init__(self):
        super().__init__('faz3_kare')
        self.al = {}
        for ad, konu in KONULAR.items():
            self.create_subscription(Image, konu, lambda m, ad=ad: self.al.setdefault(ad, m), SENSOR_QOS)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    rclpy.init()
    n = Kare()
    t = time.time()
    while time.time() - t < 8 and len(n.al) < 3:
        rclpy.spin_once(n, timeout_sec=0.2)
    parca = []
    for ad, m in n.al.items():
        a = dizi(m)
        print(ad, m.encoding, a.shape, 'degerler', np.unique(a)[:12])
        if ad == 'kamera':
            img = a[..., ::-1] if m.encoding == 'rgb8' else a
        elif ad == 'maske':
            img = RENK[np.minimum(a, 7)][..., ::-1]
        else:   # class + 1 labels
            img = RENK[np.where(a == 0, 7, a.astype(np.int16) - 1)][..., ::-1]
        img = cv2.resize(np.ascontiguousarray(img), (480, 360), interpolation=cv2.INTER_NEAREST)
        cv2.putText(img, ad, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        parca.append(img)
    if parca:
        cv2.imwrite(os.path.join(out, f'kare_{time.strftime("%H%M%S")}.png'), np.concatenate(parca, 1))
    rclpy.shutdown()


if __name__ == '__main__':
    main()
