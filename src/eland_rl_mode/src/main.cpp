/****************************************************************************
 * Entry point for the RL Landing mode (see rl_landing_mode.hpp).
 ****************************************************************************/
#include <px4_ros2/components/node_with_mode.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rl_landing_mode.hpp>

using RlLandingNode = px4_ros2::NodeWithMode<eland_rl::RlLandingMode>;

int main(int argc, char* argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RlLandingNode>("rl_landing_mode", /*enable_debug_output=*/true));
  rclcpp::shutdown();
  return 0;
}
