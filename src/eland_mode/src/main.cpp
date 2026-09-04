/****************************************************************************
 * Entry point for the Emergency Landing mode.
 *
 * NodeWithMode owns the rclcpp node, constructs the mode against it and calls
 * doRegister() for us, logging and shutting down if registration is rejected.
 * Registration is what makes PX4 aware of the mode; until it succeeds the mode
 * does not exist as far as the vehicle or the GCS are concerned.
 *
 * THE OPERATOR ESCAPE HATCH
 *
 * While this mode is registered in place of Return, a deliberate RTL lands
 * here instead of flying home, and there was no way for an operator to say
 * "no, I really do mean Return". There still is no way to change the
 * replacement at runtime -- PX4 is told which internal mode is being replaced
 * when the mode registers, and that is that.
 *
 * What can be done is to stop being registered. Publishing `false` on
 * /eland/mode_enable shuts this process down, and PX4 then falls back to its
 * own Return, which is exactly the behaviour that was measured in Phase 3
 * when the node was killed: nav_state went 23 -> 5 (AUTO_RTL) and the vehicle
 * kept flying. So the escape hatch is not a new mechanism, it is the existing
 * failure path made deliberate and reachable from the control station.
 *
 * It is one-way on purpose. Re-registering mid-flight would mean a mode
 * appearing under an operator who has just asked for it to go away; bringing
 * it back is a relaunch, which is a decision made on the ground.
 ****************************************************************************/
#include <emergency_landing_mode.hpp>
#include <px4_ros2/components/node_with_mode.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>

using EmergencyLandingNode = px4_ros2::NodeWithMode<eland::EmergencyLandingMode>;

static const std::string kNodeName = "emergency_landing_mode";

// Debug output prints the registration handshake and every mode state change,
// which is most of what there is to see while this phase is being brought up.
static const bool kEnableDebugOutput = true;

int main(int argc, char* argv[])
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<EmergencyLandingNode>(kNodeName, kEnableDebugOutput);

  auto enable_sub = node->create_subscription<std_msgs::msg::Bool>(
      "/eland/mode_enable", rclcpp::QoS(1).reliable(),
      [node](const std_msgs::msg::Bool::SharedPtr msg) {
        if (msg->data) {
          RCLCPP_INFO(node->get_logger(),
                      "mode_enable(true) ignored: the mode is already "
                      "registered, and re-registering is a relaunch");
          return;
        }
        RCLCPP_WARN(node->get_logger(),
                    "mode_enable(false): unregistering. PX4 returns to its own "
                    "Return mode, and this process exits.");
        rclcpp::shutdown();
      });

  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
