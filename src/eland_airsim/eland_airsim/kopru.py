"""AirSim -> ROS 2 bridge: what the Gazebo bridges published, from AirSim instead.

    ~/airsim-venv/bin/python -m eland_airsim.kopru --ros-args -p kamera:=asagi

Publishes, in the formats the rest of the project already reads:
  /camera/image          rgb8 640x480        (Gazebo: the RGB camera through ros_gz_image)
  /camera/camera_info    only if kamera_bilgisi: pinhole of the RGB image, HFOV from the parameter.
                         Off by default, as in Gazebo (advertised there, never published): mapping_node
                         applies any CameraInfo it receives to the 320x240 mask, so the RGB's K would
                         double its focal length and put the principal point in the corner (Faz 3, first
                         AirSim runs: candidates lost during approach). Without it, mapping_node derives K
                         from its own camera_hfov_deg for whatever size the mask has.
  /camera/segmentation   mono8 320x240, label = SORA class + 1, 0 = unknown (perception_node.remap_gt)
  /eland/gercek_poz      PoseStamped, ENU world / FLU body, ground truth (Gazebo: dynamic_pose/info)
  /clock                 AirSim's simulation time, if saat_yayinla (for use_sim_time nodes)
Wind: the parameter ruzgar_ned [m/s, north east down] is applied with simSetWind whenever it is set.

Images and the pose run on separate RPC connections, so a slow image call cannot stall the pose.
"""
import threading
import time

import numpy as np
import rclpy
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped
from rcl_interfaces.msg import SetParametersResult
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image

from . import donusum, istemci, siniflar

SENSOR_QOS = QoSProfile(depth=5, reliability=ReliabilityPolicy.BEST_EFFORT)


def _stamp(ns):
    return Time(sec=int(ns // 1_000_000_000), nanosec=int(ns % 1_000_000_000))


class Kopru(Node):
    def __init__(self):
        super().__init__('airsim_kopru')
        p = self.declare_parameter
        p('host', '')
        p('port', istemci.RPC_PORT)
        p('arac', '')                  # vehicle name; '' = the first/only vehicle
        p('kamera', 'asagi')
        p('hfov_deg', 99.7)
        p('goruntu_hz', 10.0)
        p('poz_hz', 50.0)
        p('saat_yayinla', False)
        p('segmentasyon', True)
        p('kanal_sirasi', 'bgr')       # AirSim's uncompressed images; checked in the M0 pilot
        p('cerceve', 'camera_link')
        p('dunya_cerceve', 'map')
        p('ruzgar_ned', [0.0, 0.0, 0.0])
        p('kamera_bilgisi', False)     # see the module docstring before turning this on
        g = lambda n: self.get_parameter(n).value  # noqa: E731
        host = g('host') or istemci.windows_host()
        self.img_client = istemci.connect(host, g('port'))
        self.pose_client = istemci.connect(host, g('port'))
        self.arac = g('arac')
        self.pal = siniflar.palette()
        if g('segmentasyon'):
            ok = siniflar.assign_ids(self.img_client)
            self.get_logger().info(f'segmentasyon kimlikleri atandi (sinif: eslesme var mi) {ok}')
        self.pub_img = self.create_publisher(Image, '/camera/image', SENSOR_QOS)
        self.pub_info = self.create_publisher(CameraInfo, '/camera/camera_info', SENSOR_QOS)
        self.pub_seg = self.create_publisher(Image, '/camera/segmentation', SENSOR_QOS)
        self.pub_pose = self.create_publisher(PoseStamped, '/eland/gercek_poz', 10)
        self.pub_clock = self.create_publisher(Clock, '/clock', 10) if g('saat_yayinla') else None
        self.add_on_set_parameters_callback(self._on_params)
        self._run = True
        self._threads = [threading.Thread(target=self._image_loop, daemon=True),
                         threading.Thread(target=self._pose_loop, daemon=True)]
        for t in self._threads:
            t.start()
        self.get_logger().info(f'AirSim {host}:{g("port")} bagli; kamera {g("kamera")}')

    # ------------------------------------------------------------------ parameters
    def _on_params(self, params):
        import airsim
        for prm in params:
            if prm.name == 'ruzgar_ned':
                v = list(prm.value)
                if len(v) != 3 or max(abs(x) for x in v) > 20.0:
                    return SetParametersResult(successful=False, reason='ruzgar_ned: 3 deger, her biri |v| <= 20 m/s')
                self.pose_client.simSetWind(airsim.Vector3r(*v))
                self.get_logger().info(f'ruzgar {v} m/s (NED)')
        return SetParametersResult(successful=True)

    # ------------------------------------------------------------------ loops
    def _now(self):
        return self.get_clock().now().to_msg()

    def _image_loop(self):
        import airsim
        g = lambda n: self.get_parameter(n).value  # noqa: E731
        period = 1.0 / max(g('goruntu_hz'), 0.1)
        reqs = [airsim.ImageRequest(g('kamera'), airsim.ImageType.Scene, False, False)]
        if g('segmentasyon'):
            reqs.append(airsim.ImageRequest(g('kamera'), airsim.ImageType.Segmentation, False, False))
        info = None
        while self._run and rclpy.ok():
            t0 = time.monotonic()
            try:
                res = self.img_client.simGetImages(reqs, self.arac)
            except Exception as e:  # noqa: BLE001
                self.get_logger().warning(f'goruntu alinamadi: {e}', throttle_duration_sec=5.0)
                time.sleep(0.5)
                continue
            stamp = self._now()
            rgb = np.frombuffer(res[0].image_data_uint8, np.uint8).reshape(res[0].height, res[0].width, 3)
            if g('kanal_sirasi') == 'bgr':
                rgb = rgb[..., ::-1]
            self.pub_img.publish(self._image(rgb, 'rgb8', stamp))
            if info is None:
                fx, fy, cx, cy = donusum.camera_matrix(res[0].width, res[0].height, g('hfov_deg'))
                info = CameraInfo(width=res[0].width, height=res[0].height, distortion_model='plumb_bob',
                                  d=[0.0] * 5, k=[fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0],
                                  r=[1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0], p=[fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0])
            if g('kamera_bilgisi'):
                info.header.stamp, info.header.frame_id = stamp, g('cerceve')
                self.pub_info.publish(info)
            if len(res) > 1:
                seg = np.frombuffer(res[1].image_data_uint8, np.uint8).reshape(res[1].height, res[1].width, 3)
                labels = siniflar.decode(seg, self.pal, g('kanal_sirasi'))
                self.pub_seg.publish(self._image(labels, 'mono8', stamp))
            time.sleep(max(0.0, period - (time.monotonic() - t0)))

    def _pose_loop(self):
        g = lambda n: self.get_parameter(n).value  # noqa: E731
        period = 1.0 / max(g('poz_hz'), 1.0)
        while self._run and rclpy.ok():
            t0 = time.monotonic()
            try:
                # ground truth, not getMultirotorState: with PX4 that one carries PX4's own estimate
                k = self.pose_client.simGetGroundTruthKinematics(self.arac)
                if self.pub_clock is not None:
                    self.pub_clock.publish(Clock(clock=_stamp(self.pose_client.getMultirotorState(self.arac).timestamp)))
            except Exception as e:  # noqa: BLE001
                self.get_logger().warning(f'durum alinamadi: {e}', throttle_duration_sec=5.0)
                time.sleep(0.5)
                continue
            pos, q = donusum.ned_pose_to_enu(k.position.x_val, k.position.y_val, k.position.z_val,
                                             k.orientation.w_val, k.orientation.x_val, k.orientation.y_val,
                                             k.orientation.z_val)
            msg = PoseStamped()
            msg.header.stamp, msg.header.frame_id = self._now(), g('dunya_cerceve')
            msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = pos
            msg.pose.orientation.w, msg.pose.orientation.x, msg.pose.orientation.y, msg.pose.orientation.z = q
            self.pub_pose.publish(msg)
            time.sleep(max(0.0, period - (time.monotonic() - t0)))

    def _image(self, arr, encoding, stamp):
        arr = np.ascontiguousarray(arr)
        msg = Image(height=arr.shape[0], width=arr.shape[1], encoding=encoding, is_bigendian=0,
                    step=arr.shape[1] * (3 if arr.ndim == 3 else 1), data=arr.tobytes())
        msg.header.stamp, msg.header.frame_id = stamp, self.get_parameter('cerceve').value
        return msg

    def destroy_node(self):
        self._run = False
        for c in (self.img_client, self.pose_client):
            try:
                c.client.close()
            except Exception:  # noqa: BLE001
                pass
        super().destroy_node()


def main():
    rclpy.init()
    node = Kopru()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
