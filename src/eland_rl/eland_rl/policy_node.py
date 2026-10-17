"""ROS 2 node: run the trained policy against Gazebo + PX4 (F4).

Every `period_s` (0.25 s, the training step) it builds the same 2x128x128
observation the environment builds, asks the policy for an action, and
publishes that action as a velocity in NED on /eland/rl/hiz_komutu, which the
RL Landing mode (eland_rl_mode) hands to PX4.

WHERE THE OBSERVATION COMES FROM
  label_source = 'gt'     the photo's class mask seen from the camera's true
                          pose (gz dynamic_pose), by eland_rl.camera -- the
                          very projection the policy was trained on. Isolates
                          the PX4 side of the transfer.
  label_source = 'topic'  a label image (e.g. /eland/v3/etiket, mono8,
                          class + label_offset), sampled at the pixels
                          INTER_NEAREST would keep. The real perception chain.
Depth is always the flat-ground depth from the camera pose: on a flat world
that is exactly what a depth sensor would report.

WHERE THE POSE COMES FROM
  pose_source = 'gz'      Gazebo's dynamic_pose (default, unchanged)
  pose_source = 'topic'   a PoseStamped, ENU world / FLU body: in AirSim the
                          bridge's /eland/gercek_poz (eland_airsim.kopru)

THE OBSERVATION FOLLOWS THE TRAINING RUN
The run's args.json (next to model_path, or run_args) sets what the
environment fed the policy: the reward preset decides the third channel
(zemin_v1: landable and clear of the buffer classes; otherwise SORA 3 m), and
--binary the first. Without args.json the node keeps its old observation.
kalkan_m >= 0 puts evaluate.py's SORA shield (pilots.shield) behind the policy.

The action is body-relative (1 = nose = image up, counter-clockwise in 45
degree steps); it is turned into a world velocity with the vehicle's current
heading, as the environment does.
"""
import csv
import json
import math
import os
import threading
import time

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Int8

from .camera import Camera, ground_hits, nearest_source_index, sora_channel
from .env import REWARD_PRESETS, EnvConfig
from .pilots import shield
from .scene import Scene

N_CLASSES = 8


def rotation_from_quat(x, y, z, w):
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


class PolicyNode(Node):
    def __init__(self):
        super().__init__('rl_politika')
        p = self.declare_parameter
        p('model_path', '')
        p('label_source', 'gt')
        p('label_topic', '/eland/v3/etiket')
        p('label_offset', 1)
        p('scene_jpg', '/home/arda/v3_test/foto/fotoo/DJI_0097.JPG')
        p('scene_mask', '/home/arda/v3_test/maske/fotomask/DJI_0097.png')
        p('scene_size_m', [64.02, 42.68])
        p('gz_world', 'orto_dji0097')
        p('gz_model', 'x500_seg_cam_rgb_down_0')
        p('camera_offset_m', 0.10)
        p('ground_z_m', 0.02)
        p('period_s', 0.25)
        p('v_lateral', 1.0)
        p('v_descend', 2.0)
        p('depth_norm_m', 40.0)
        p('log_csv', '')
        p('publish_view', True)
        p('pose_source', 'gz')
        p('pose_topic', '/eland/gercek_poz')
        p('run_args', '')
        p('kalkan_m', -1.0)
        g = lambda k: self.get_parameter(k).value  # noqa: E731
        from stable_baselines3 import PPO
        self.model = PPO.load(g('model_path'), device='cpu')
        self.n_channels = int(self.model.observation_space.shape[0])
        self.cfg, self.cfg_note = self.training_config(g('run_args') or os.path.join(
            os.path.dirname(os.path.abspath(g('model_path'))), 'args.json'))
        self.kalkan_m = float(g('kalkan_m'))
        self.source = g('label_source')
        self.offset = int(g('label_offset'))
        self.cam_off, self.ground_z = float(g('camera_offset_m')), float(g('ground_z_m'))
        self.v_lat, self.v_down, self.dnorm = float(g('v_lateral')), float(g('v_descend')), float(g('depth_norm_m'))
        self.model_name = g('gz_model')
        self.cam = Camera(128)
        self.scene = None
        if self.source == 'gt':
            self.scene = Scene.from_messi(g('scene_jpg'), g('scene_mask'), size_m=tuple(g('scene_size_m')))
        self.rows = nearest_source_index(240, 128)
        self.cols = nearest_source_index(320, 128)
        self.label = None
        self.pose = None
        self.lock = threading.Lock()
        rel = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self.pub = self.create_publisher(TwistStamped, '/eland/rl/hiz_komutu', rel)
        self.pub_a = self.create_publisher(Int8, '/eland/rl/eylem', rel)
        self.pub_view = self.create_publisher(Image, '/eland/rl/gorus', 1) if g('publish_view') else None
        if self.source == 'topic':
            self.create_subscription(Image, g('label_topic'), self.on_label, 1)
        if g('pose_source') == 'topic':
            self.create_subscription(PoseStamped, g('pose_topic'), self.on_pose_topic, 10)
            pose_from = g('pose_topic')
        else:
            from gz.msgs10.pose_v_pb2 import Pose_V
            from gz.transport13 import Node as GzNode
            self.gz = GzNode()
            pose_from = f'/world/{g("gz_world")}/dynamic_pose/info'
            if not self.gz.subscribe(Pose_V, pose_from, self.on_pose):
                raise RuntimeError(f'{pose_from}: cannot subscribe')
        self.log = None
        if g('log_csv'):
            self.log_f = open(g('log_csv'), 'w', newline='')
            self.log = csv.writer(self.log_f)
            self.log.writerow(['t_wall', 't_sim', 'x', 'y', 'z_cam', 'yaw_deg', 'tilt_deg', 'action',
                               'safe_share', 'majority', 'vn', 've', 'vd', 'infer_ms', 'kalkan'])
        self.safe = np.zeros(N_CLASSES, bool)
        self.safe[[0, 1]] = True
        ang = np.radians(np.arange(8) * 45.0)
        self.lateral = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.create_timer(float(g('period_s')), self.tick)
        self.get_logger().info(f'policy {g("model_path")}, labels from {self.source}, pose from {pose_from}; '
                               f'{self.cfg_note}; kalkan {"yok" if self.kalkan_m < 0 else f"{self.kalkan_m} m"}')

    @staticmethod
    def training_config(path):
        """The EnvConfig the policy was trained with, as far as the observation goes."""
        if not os.path.exists(path):
            return EnvConfig(), 'args.json yok: eski gozlem (SORA 3 m)'
        a = json.load(open(path))
        cfg = EnvConfig(binary=bool(a.get('binary', False)), obs_mode=a.get('obs', 'sem_depth'),
                        **REWARD_PRESETS[a.get('reward', 'paper')])
        third = (f'tampon {cfg.buffer_m} m {tuple(cfg.buffer_classes)}' if cfg.success_rule == 'zemin'
                 else f'SORA {cfg.sora_m} m')
        return cfg, f'egitim: odul {a.get("reward")}, gozlem {cfg.obs_mode}, 3. kanal {third}'

    def on_pose_topic(self, msg):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        p, o = msg.pose.position, msg.pose.orientation
        with self.lock:
            self.pose = (t, np.array([p.x, p.y, p.z]), rotation_from_quat(o.x, o.y, o.z, o.w))

    def on_pose(self, msg):
        t = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
        for ps in msg.pose:
            if ps.name == self.model_name:
                o = ps.orientation
                with self.lock:
                    self.pose = (t, np.array([ps.position.x, ps.position.y, ps.position.z]),
                                 rotation_from_quat(o.x, o.y, o.z, o.w))
                return

    def on_label(self, msg):
        img = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width)
        with self.lock:
            self.label = img.copy()

    def observe(self, c, R):
        if self.source == 'gt':
            sem, depth = self.cam.semantic_depth(self.scene, c, R)
        else:
            with self.lock:
                lab = self.label
            if lab is None:
                return None
            if lab.shape != (240, 320):
                import cv2
                lab = cv2.resize(lab, (320, 240), interpolation=cv2.INTER_NEAREST)
            cls = lab[np.ix_(self.rows, self.cols)].astype(np.int16) - self.offset
            sem = np.where((cls >= 0) & (cls < N_CLASSES - 1), cls, N_CLASSES - 1).astype(np.uint8)
            _, _, depth = ground_hits(self.cam.rays, c, R)
        d = np.where(np.isfinite(depth), depth, self.dnorm)
        cfg = self.cfg
        ch0 = self.safe[sem].astype(np.float32) if cfg.binary else sem.astype(np.float32) / (N_CLASSES - 1)
        chans = [ch0, np.clip(d / self.dnorm, 0, 1).astype(np.float32)]
        if self.n_channels == 3:                                   # observation v2: + SORA-safe mask
            if cfg.success_rule == 'zemin':                        # as env._observe, amendment 9
                sora = sora_channel(sem, c[2], cfg.buffer_m, hazard_classes=cfg.buffer_classes)
            else:
                sora = sora_channel(sem, c[2], cfg.sora_m)
            chans.append(sora.astype(np.float32))
        obs = np.stack(chans)
        return obs, sem

    def publish_view(self, sem, a, altitude_m):
        img = view_image(sem, a, altitude_m, float(self.safe[sem].mean()))
        m = Image()
        m.header.stamp = self.get_clock().now().to_msg()
        m.height, m.width = img.shape[:2]
        m.encoding = 'rgb8'
        m.step = 3 * m.width
        m.data = img.tobytes()
        self.pub_view.publish(m)

    def tick(self):
        with self.lock:
            pose = self.pose
        if pose is None:
            return
        t_sim, p, R = pose
        c = p + R @ np.array([0.0, 0.0, self.cam_off])
        c[2] -= self.ground_z
        got = self.observe(c, R)
        if got is None:
            return
        obs, sem = got
        t0 = time.perf_counter()
        a = int(self.model.predict(obs, deterministic=True)[0])
        ms = (time.perf_counter() - t0) * 1000
        overridden = False
        if self.kalkan_m >= 0 and self.n_channels == 3:
            a, overridden = shield(a, obs, c[2], self.kalkan_m)
        yaw = math.atan2(R[1, 0], R[0, 0])
        if a == 9:
            v_enu = np.array([0.0, 0.0, -self.v_down])
        elif a == 0:
            v_enu = np.zeros(3)
        else:
            bx, by = self.lateral[a - 1] * self.v_lat
            v_enu = np.array([math.cos(yaw) * bx - math.sin(yaw) * by, math.sin(yaw) * bx + math.cos(yaw) * by, 0.0])
        vn, ve, vd = float(v_enu[1]), float(v_enu[0]), float(-v_enu[2])
        m = TwistStamped()
        m.header.stamp = self.get_clock().now().to_msg()
        m.header.frame_id = 'ned'
        m.twist.linear.x, m.twist.linear.y, m.twist.linear.z = vn, ve, vd
        self.pub.publish(m)
        self.pub_a.publish(Int8(data=a))
        if self.pub_view is not None:
            self.publish_view(sem, a, c[2])
        if self.log:
            tilt = math.degrees(math.acos(max(-1.0, min(1.0, R[2, 2]))))
            self.log.writerow([f'{time.time():.3f}', f'{t_sim:.3f}', f'{c[0]:.3f}', f'{c[1]:.3f}', f'{c[2]:.3f}',
                               f'{math.degrees(yaw):.1f}', f'{tilt:.2f}', a, f'{self.safe[sem].mean():.3f}',
                               int(np.bincount(sem.ravel(), minlength=N_CLASSES).argmax()),
                               f'{vn:.2f}', f'{ve:.2f}', f'{vd:.2f}', f'{ms:.2f}', int(overridden)])
            self.log_f.flush()


def view_image(sem, a, altitude_m, safe_share):
    """What the policy saw (128x128 classes, x4) and what it chose: arrow, ring or square."""
    import cv2
    from eland_common import classes
    colours = np.array([classes.CLASS_COLORS[i] for i in range(N_CLASSES)], np.uint8)
    img = cv2.resize(colours[sem], (512, 512), interpolation=cv2.INTER_NEAREST)
    c = (256, 256)
    white, black = (255, 255, 255), (0, 0, 0)
    if a == 9:
        name = 'ALCAL'
        for col, w in ((black, 7), (white, 3)):
            cv2.circle(img, c, 40, col, w, cv2.LINE_AA)
            cv2.drawMarker(img, c, col, cv2.MARKER_TILTED_CROSS, 40, w, cv2.LINE_AA)
    elif a == 0:
        name = 'DUR'
        for col, w in ((black, 7), (white, 3)):
            cv2.rectangle(img, (226, 226), (286, 286), col, w, cv2.LINE_AA)
    else:
        th = math.radians((a - 1) * 45.0)          # from the nose (image up), counter-clockwise
        tip = (int(256 - 150 * math.sin(th)), int(256 - 150 * math.cos(th)))
        name = ['ILERI', 'SOL-ILERI', 'SOL', 'SOL-GERI', 'GERI', 'SAG-GERI', 'SAG', 'SAG-ILERI'][a - 1]
        for col, w in ((black, 9), (white, 4)):
            cv2.arrowedLine(img, c, tip, col, w, cv2.LINE_AA, tipLength=0.25)
    bar = np.full((64, 512, 3), 24, np.uint8)
    cv2.putText(bar, f'{a} {name}', (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, white, 2, cv2.LINE_AA)
    cv2.putText(bar, f'kamera {altitude_m:5.1f} m   guvenli pay {100 * safe_share:4.1f} %', (10, 54),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
    return np.ascontiguousarray(np.concatenate([img, bar], 0))


def main():
    rclpy.init()
    n = PolicyNode()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    finally:
        n.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
