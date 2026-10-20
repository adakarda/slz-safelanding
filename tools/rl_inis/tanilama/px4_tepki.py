"""F1 identification flight: PX4's closed-loop answer to velocity steps.

Run after run_sim.sh --takeoff 25 has the vehicle hovering. Streams offboard
velocity setpoints (the same uORB path the RL mode will use), switches to
offboard, flies a fixed step programme and then a random 10-action sequence
like the policy's, and logs everything with PX4 timestamps to an .npz.

    python3 px4_tepki.py --ros-args -p cikti:=/home/arda/rl_inis/tanilama/kos1.npz
"""
import math

import numpy as np
import rclpy
from px4_msgs.msg import (OffboardControlMode, TrajectorySetpoint, VehicleAttitude,
                          VehicleCommand, VehicleLocalPosition, VehicleStatus)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy

OUT_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     history=HistoryPolicy.KEEP_LAST, depth=1)
IN_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE,
                    history=HistoryPolicy.KEEP_LAST, depth=1)
HZ = 50.0
NAV_OFFBOARD = 14


def programme(rng):
    """[(duration_s, (vn, ve, vd))]: steps first, then 160 random policy-like actions."""
    p = [(4, (0, 0, 0)),
         (5, (1, 0, 0)), (4, (0, 0, 0)), (5, (-1, 0, 0)), (4, (0, 0, 0)),
         (5, (0, 1, 0)), (4, (0, 0, 0)), (5, (0, -1, 0)), (4, (0, 0, 0)),
         (5, (math.sqrt(.5), math.sqrt(.5), 0)), (4, (0, 0, 0)),
         (3, (0, 0, 2)), (4, (0, 0, 0))]
    ang = np.radians(np.arange(8) * 45.0)
    for a in rng.integers(0, 10, 160):
        if a == 0:
            v = (0, 0, 0)
        elif a == 9:
            v = (0, 0, 2)
        else:
            v = (math.cos(ang[a - 1]), math.sin(ang[a - 1]), 0)
        p.append((0.25, v))
    p.append((4, (0, 0, 0)))
    return p


class Tepki(Node):
    def __init__(self):
        super().__init__('px4_tepki')
        self.cikti = self.declare_parameter('cikti', '/home/arda/rl_inis/tanilama/kos.npz').value
        self.min_irtifa = self.declare_parameter('min_irtifa_m', 10.0).value
        self.plan = programme(np.random.default_rng(int(self.declare_parameter('tohum', 0).value)))
        self.lp = None
        self.nav = None
        self.kayit_lp, self.kayit_att, self.kayit_sp = [], [], []
        self.create_subscription(VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1', self.on_lp, OUT_QOS)
        self.create_subscription(VehicleAttitude, '/fmu/out/vehicle_attitude', self.on_att, OUT_QOS)
        self.create_subscription(VehicleStatus, '/fmu/out/vehicle_status_v4', self.on_st, OUT_QOS)
        self.pub_mode = self.create_publisher(OffboardControlMode, '/fmu/in/offboard_control_mode', IN_QOS)
        self.pub_sp = self.create_publisher(TrajectorySetpoint, '/fmu/in/trajectory_setpoint', IN_QOS)
        self.pub_cmd = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', IN_QOS)
        self.durum = 'bekle'
        self.sayac = 0
        self.yaw = None
        self.i, self.t_seg = 0, 0.0
        self.create_timer(1.0 / HZ, self.dongu)

    def on_lp(self, m):
        self.lp = m
        self.kayit_lp.append((m.timestamp, m.x, m.y, m.z, m.vx, m.vy, m.vz, m.ax, m.ay, m.az, m.heading))

    def on_att(self, m):
        self.kayit_att.append((m.timestamp, *m.q))

    def on_st(self, m):
        self.nav = m.nav_state

    def gonder(self, v):
        ts = int(self.get_clock().now().nanoseconds / 1000)
        self.pub_mode.publish(OffboardControlMode(timestamp=ts, position=False, velocity=True))
        nan = float('nan')
        sp = TrajectorySetpoint(timestamp=ts, position=[nan, nan, nan], velocity=[float(c) for c in v],
                                acceleration=[nan, nan, nan], jerk=[nan, nan, nan], yaw=float(self.yaw), yawspeed=nan)
        self.pub_sp.publish(sp)
        if self.lp is not None:
            self.kayit_sp.append((self.lp.timestamp, *[float(c) for c in v]))

    def offboard_iste(self):
        ts = int(self.get_clock().now().nanoseconds / 1000)
        self.pub_cmd.publish(VehicleCommand(timestamp=ts, command=VehicleCommand.VEHICLE_CMD_DO_SET_MODE, param1=1.0,
                                            param2=6.0, target_system=1, target_component=1, source_system=1,
                                            source_component=1, from_external=True))

    def dongu(self):
        if self.lp is None or self.nav is None:
            return
        if self.durum == 'bekle':
            if -self.lp.z > 20.0 and abs(self.lp.vz) < 0.3:
                self.yaw = self.lp.heading
                self.durum = 'isin'
                self.get_logger().info(f'hover {-self.lp.z:.1f} m, setpoint akisi basliyor')
            return
        if self.durum == 'isin':
            self.gonder((0, 0, 0))
            self.sayac += 1
            if self.sayac >= HZ * 2 and self.sayac % int(HZ) == 0:
                if self.nav == NAV_OFFBOARD:
                    self.durum = 'program'
                    self.get_logger().info('offboard; program basladi')
                else:
                    self.offboard_iste()
            return
        if self.durum == 'program':
            # segments are timed on PX4's (simulated) clock, so the real-time factor does not matter
            t = self.lp.timestamp * 1e-6
            if self.t_seg == 0.0:
                self.t_seg = t
            sure, v = self.plan[self.i]
            if t - self.t_seg >= sure - 1e-6:
                self.i += 1
                self.t_seg = t
                if self.i >= len(self.plan):
                    self.durum = 'bitti'
                    self.kaydet()
                    return
                sure, v = self.plan[self.i]
            if v[2] > 0 and -self.lp.z < self.min_irtifa:
                v = (v[0], v[1], 0.0)
            self.gonder(v)
            return
        if self.durum == 'bitti':
            self.gonder((0, 0, 0))

    def kaydet(self):
        np.savez(self.cikti, lp=np.array(self.kayit_lp, float), att=np.array(self.kayit_att, float),
                 sp=np.array(self.kayit_sp, float))
        self.get_logger().info(f'kaydedildi: {self.cikti} (lp {len(self.kayit_lp)}, att {len(self.kayit_att)}, '
                               f'sp {len(self.kayit_sp)}); hover devam ediyor, sim kapatilabilir')


def main():
    rclpy.init()
    n = Tepki()
    try:
        while rclpy.ok() and n.durum != 'bitti':
            rclpy.spin_once(n, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    n.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
