#!/usr/bin/env python3
"""Perception disturbances between the mask and everything after it (Asama 5).

    tools/veri/bozucu.py TUR SEVIYE --tohum N

Subscribes /eland/semantic_mask, republishes on /eland/semantic_mask_bozuk.
Nothing changes unless the pipeline is pointed at the new topic -- the
detector, mapping and HUD nodes already take `mask_topic` as a parameter, so
the runner switches them through the parameter file; no node is edited.

TUR / SEVIYE:
    sinir    1|2      class boundaries jittered: every pixel within SEVIYE px
                      of a boundary takes the class of a random neighbour
                      within +-SEVIYE px
    cevir    0.005|0.02  that fraction of pixels flipped to another class
    kayip    0.05     with this probability per frame, the safe region under
                      the image centre is lost (set to UNKNOWN) for the frame
    gecikme  0.1|0.2|0.3  every frame published that many seconds late, with
                      its own capture stamp
    tekrar   1|2|3    content updated only every SEVIYE+1 frames; the frames
                      in between repeat the old mask under the new stamp
                      (staleness that the stamp does not reveal)

Seeded (numpy Generator), so a disturbed run can be repeated. The Gazebo
labels are perfect; a trained model's errors will have another distribution,
so the levels are parameters, not a claim about that model.
"""
import argparse
import collections
import time

import cv2
import numpy as np
import rclpy
import rclpy.executors
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from sensor_msgs.msg import Image

SENSOR = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                    durability=DurabilityPolicy.VOLATILE,
                    history=HistoryPolicy.KEEP_LAST, depth=5)
SAFE = (0, 1)
UNKNOWN = 7
N_CLASSES = 8


class Bozucu(Node):
    def __init__(self, a):
        super().__init__('veri_bozucu')
        self.a = a
        self.rng = np.random.default_rng(a.tohum)
        self.pub = self.create_publisher(Image, a.cikis, SENSOR)
        self.create_subscription(Image, a.giris, self.on_mask, SENSOR)
        self.queue = collections.deque()
        self.held = None
        self.count = 0
        self.n_kayip = 0
        if a.tur == 'gecikme':
            self.create_timer(0.005, self.flush)
        self.get_logger().info(f'bozucu: {a.tur} {a.seviye} (tohum {a.tohum}) '
                               f'{a.giris} -> {a.cikis}')

    def disturb(self, m):
        a, rng = self.a, self.rng
        if a.tur == 'sinir':
            k = int(a.seviye)
            edge = np.zeros(m.shape, bool)
            edge[:, :-1] |= m[:, :-1] != m[:, 1:]
            edge[:, 1:] |= m[:, 1:] != m[:, :-1]
            edge[:-1, :] |= m[:-1, :] != m[1:, :]
            edge[1:, :] |= m[1:, :] != m[:-1, :]
            band = cv2.dilate(edge.astype(np.uint8), np.ones((2 * k + 1, 2 * k + 1), np.uint8)) > 0
            ys, xs = np.nonzero(band)
            dy = rng.integers(-k, k + 1, len(ys))
            dx = rng.integers(-k, k + 1, len(xs))
            out = m.copy()
            out[ys, xs] = m[np.clip(ys + dy, 0, m.shape[0] - 1),
                            np.clip(xs + dx, 0, m.shape[1] - 1)]
            return out
        if a.tur == 'cevir':
            out = m.copy()
            n = int(round(a.seviye * m.size))
            idx = rng.choice(m.size, n, replace=False)
            shift = rng.integers(1, N_CLASSES, n)
            flat = out.reshape(-1)
            flat[idx] = (flat[idx] + shift) % N_CLASSES
            return out
        if a.tur == 'kayip':
            if rng.random() >= a.seviye:
                return m
            safe = np.isin(m, SAFE).astype(np.uint8)
            _, labels = cv2.connectedComponents(safe, connectivity=8)
            lab = labels[m.shape[0] // 2, m.shape[1] // 2]
            if lab == 0:
                return m
            self.n_kayip += 1
            out = m.copy()
            out[labels == lab] = UNKNOWN
            return out
        return m

    def on_mask(self, msg):
        rows = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)
        m = rows[:, :msg.width].copy()
        self.count += 1
        if self.a.tur == 'tekrar':
            if self.held is None or (self.count - 1) % (int(self.a.seviye) + 1) == 0:
                self.held = m
            out = self.held
        else:
            out = self.disturb(m)
        o = Image()
        o.header = msg.header
        o.height, o.width = out.shape
        o.encoding = msg.encoding or 'mono8'
        o.is_bigendian = msg.is_bigendian
        o.step = out.shape[1]
        o.data = out.astype(np.uint8).tobytes()
        if self.a.tur == 'gecikme':
            self.queue.append((time.monotonic() + self.a.seviye, o))
        else:
            self.pub.publish(o)

    def flush(self):
        now = time.monotonic()
        while self.queue and self.queue[0][0] <= now:
            self.pub.publish(self.queue.popleft()[1])


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('tur', choices=['sinir', 'cevir', 'kayip', 'gecikme', 'tekrar'])
    p.add_argument('seviye', type=float)
    p.add_argument('--tohum', type=int, default=1)
    p.add_argument('--giris', default='/eland/semantic_mask')
    p.add_argument('--cikis', default='/eland/semantic_mask_bozuk')
    a = p.parse_args()
    rclpy.init()
    node = Bozucu(a)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.get_logger().info(f'{node.count} kare, {node.n_kayip} bolge kaybi')
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
