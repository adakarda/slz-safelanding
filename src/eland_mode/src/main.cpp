/****************************************************************************
 * Entry point for the Emergency Landing mode.
 *
 * NodeWithMode owns the rclcpp node, constructs the mode against it and calls
 * doRegister() for us, logging and shutting down if registration is rejected.
 * Registration is what makes PX4 aware of the mode; until it succeeds the mode
 * does not exist as far as the vehicle or the GCS are concerned.
 ****************************************************************************/
#include <emergency_landing_mode.hpp>
#include <px4_ros2/components/node_with_mode.hpp>
#include <rclcpp/rclcpp.hpp>

using EmergencyLandingNode = px4_ros2::NodeWithMode<eland::EmergencyLandingMode>;

static const std::string kNodeName = "emergency_landing_mode";

// Debug output prints the registration handshake and every mode state change,
// which is most of what there is to see while this phase is being brought up.
static const bool kEnableDebugOutput = true;

int main(int argc, char* argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<EmergencyLandingNode>(kNodeName, kEnableDebugOutput));
  rclcpp::shutdown();
  return 0;
}
