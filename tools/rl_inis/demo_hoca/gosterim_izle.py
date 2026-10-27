"""Gosterim goruntuleyicisi (28.10): v4 paneli ve RL komut ekrani, sabit yerlerde iki OpenCV penceresi. Iki
rqt_image_view ayni anda acilinca ikincisi bos kaliyordu.

    source /opt/ros/jazzy/setup.bash; python3 gosterim_izle.py
"""
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

PENCERE = {  # topic: (title, x, y, width)
    '/eland/v3/panel': ('Segmentasyon v4 | AirSim etiketi', 0, 0, 1180),
    '/eland/rl/gorus': ('RL komutlari', 1190, 0, 420),
}


def goruntu(m):
    a = np.frombuffer(m.data, np.uint8)
    if m.encoding in ('rgb8', 'bgr8'):
        a = a.reshape(m.height, m.step)[:, :m.width * 3].reshape(m.height, m.width, 3)
        return a[:, :, ::-1].copy() if m.encoding == 'rgb8' else a.copy()
    if m.encoding == 'mono8':
        return cv2.cvtColor(a.reshape(m.height, m.step)[:, :m.width], cv2.COLOR_GRAY2BGR)
    return None


class Izle(Node):
    def __init__(self):
        super().__init__('gosterim_izle')
        self.son = {}
        for konu in PENCERE:
            for qos in (qos_profile_sensor_data, 1):
                self.create_subscription(Image, konu, lambda m, k=konu: self.son.__setitem__(k, m), qos)
        for konu, (ad, x, y, w) in PENCERE.items():
            cv2.namedWindow(ad, cv2.WINDOW_NORMAL)
            bos = np.full((240, w, 3), 30, np.uint8)
            cv2.putText(bos, 'bekleniyor...', (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)
            cv2.imshow(ad, bos)
            cv2.moveWindow(ad, x, y)


def main():
    rclpy.init()
    n = Izle()
    boy = {}
    while rclpy.ok():
        rclpy.spin_once(n, timeout_sec=0.05)
        for konu, m in list(n.son.items()):
            img = goruntu(m)
            if img is None:
                continue
            ad, x, y, w = PENCERE[konu]
            h = int(img.shape[0] * w / img.shape[1])
            if boy.get(konu) != (w, h):
                cv2.resizeWindow(ad, w, h)
                boy[konu] = (w, h)
            cv2.imshow(ad, cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA))
        n.son.clear()
        if cv2.waitKey(10) == 27:
            break
    n.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
