"""The control station's "0" key, for the RL mode.

    python3 -m eland_airsim.rl_tetik        (run_airsim.sh --station --rl starts it)

The control station (eland_viz, not changed) answers "0" by asking PX4 for nav_state 23, the first external
mode, which is Emergency Landing. In an RL run that mode is not registered and RL Landing sits at another
nav_state, so "0" would do nothing. This node watches /fmu/in/vehicle_command for exactly that request and
answers it by asking the RL mode to activate (/eland/rl/etkinlestir), the way the test runner does. The
station has already stopped re-asserting manual control when "0" was pressed, so the two do not fight.
"""
import rclpy
from px4_msgs.msg import VehicleCommand
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool

CMD_SET_NAV_STATE = 100001
NAV_EXTERNAL1 = 23


class RlTetik(Node):
    def __init__(self):
        super().__init__('rl_tetik')
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE,
                         history=HistoryPolicy.KEEP_LAST, depth=5)
        self.pub = self.create_publisher(Bool, '/eland/rl/etkinlestir', 10)
        self.create_subscription(VehicleCommand, '/fmu/in/vehicle_command', self.on_cmd, qos)
        self.get_logger().info('istasyonun "0" tusu RL modunu tetikleyecek')

    def on_cmd(self, m):
        if m.command == CMD_SET_NAV_STATE and round(m.param1) == NAV_EXTERNAL1:
            self.pub.publish(Bool(data=True))
            self.get_logger().info('"0" goruldu: RL Landing etkinlestiriliyor')


def main():
    rclpy.init()
    n = RlTetik()
    try:
        rclpy.spin(n)
    except KeyboardInterrupt:
        pass
    finally:
        n.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
