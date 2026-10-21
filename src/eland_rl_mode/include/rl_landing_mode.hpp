/****************************************************************************
 * RL Landing -- the PX4 flight mode that executes the RL policy's commands.
 *
 * The policy (eland_rl, Python) picks one of ten high-level actions every
 * 0.25 s and publishes it as a velocity on /eland/rl/hiz_komutu
 * (geometry_msgs/TwistStamped, linear = velocity in NED, m/s). This mode turns
 * that into a TrajectorySetpoint and nothing more: it holds no opinion about
 * where to land. docs/onkayit/rl_f0_onkayit.md, decision D5.
 *
 * Three rules, all about what happens when the policy is NOT talking:
 *   * a command older than command_timeout_s is not followed; the vehicle
 *     holds (zero velocity) until a fresh one arrives,
 *   * below target_altitude_m (5 m, the training episode's end) the policy is
 *     no longer listened to: horizontal position is frozen and the vehicle
 *     descends at touchdown_speed_m_s, by velocity, as eland_mode's COMMIT
 *     does and for the same reason (PX4's land detector needs low thrust),
 *   * heading is frozen at activation; the policy's actions are body-relative
 *     and it was trained with a heading held through the episode.
 *
 * Registered standalone: it replaces no internal mode, so Emergency Landing
 * keeps its place as the Return replacement. Publishing true on
 * /eland/rl/etkinlestir asks PX4 to switch to this mode (VehicleCommand
 * 100001 with this mode's own nav_state), which is what the test runner uses.
 ****************************************************************************/
#pragma once

#include <Eigen/Core>
#include <geometry_msgs/msg/twist_stamped.hpp>
#include <px4_msgs/msg/vehicle_command.hpp>
#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/trajectory.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <px4_ros2/vehicle_state/land_detected.hpp>
#include <rclcpp/rclcpp.hpp>
#include <std_msgs/msg/bool.hpp>
#include <std_msgs/msg/string.hpp>

#include <cmath>
#include <memory>
#include <sstream>
#include <string>

namespace eland_rl {

static const std::string kModeName = "RL Landing";

class RlLandingMode : public px4_ros2::ModeBase {
 public:
  explicit RlLandingMode(rclcpp::Node& node) : ModeBase(node, Settings{kModeName}), _node(node)
  {
    _trajectory = std::make_shared<px4_ros2::TrajectorySetpointType>(*this);
    _local_position = std::make_shared<px4_ros2::OdometryLocalPosition>(*this);
    _land_detected = std::make_shared<px4_ros2::LandDetected>(*this);

    _target_altitude_m = node.declare_parameter<double>("target_altitude_m", 5.0);
    _touchdown_speed_m_s = node.declare_parameter<double>("touchdown_speed_m_s", 0.7);
    _command_timeout_s = node.declare_parameter<double>("command_timeout_s", 0.5);
    // amendment 23: faster touchdown phase down to hizli_son_irtifa_m; < 0 (default) keeps the single speed
    _hizli_son_irtifa_m = node.declare_parameter<double>("hizli_son_irtifa_m", -1.0);
    _hizli_son_hiz_m_s = node.declare_parameter<double>("hizli_son_hiz_m_s", 2.0);

    _command_sub = node.create_subscription<geometry_msgs::msg::TwistStamped>(
        "/eland/rl/hiz_komutu", rclcpp::QoS(10).reliable(),
        [this](const geometry_msgs::msg::TwistStamped::SharedPtr msg) {
          _command = Eigen::Vector3f(static_cast<float>(msg->twist.linear.x),
                                     static_cast<float>(msg->twist.linear.y),
                                     static_cast<float>(msg->twist.linear.z));
          _command_time = _node.now();
          _have_command = true;
        });
    _activate_sub = node.create_subscription<std_msgs::msg::Bool>(
        "/eland/rl/etkinlestir", rclcpp::QoS(1).reliable(),
        [this](const std_msgs::msg::Bool::SharedPtr msg) {
          if (msg->data) {
            requestActivation();
          }
        });
    _vehicle_command_pub = node.create_publisher<px4_msgs::msg::VehicleCommand>(
        "/fmu/in/vehicle_command", rclcpp::QoS(1).best_effort());
    _state_pub = node.create_publisher<std_msgs::msg::String>("/eland/rl/mod_durumu",
                                                              rclcpp::QoS(10).reliable());
  }

  void onActivate() override
  {
    _heading = _local_position->heading();
    _touchdown = false;
    _completed = false;
    _have_command = false;
    RCLCPP_INFO(_node.get_logger(), "RL Landing active, heading frozen at %.1f deg",
                _heading * 180.0 / M_PI);
  }

  void onDeactivate() override { RCLCPP_INFO(_node.get_logger(), "RL Landing inactive"); }

  void updateSetpoint(float /*dt_s*/) override
  {
    const Eigen::Vector3f pos = _local_position->positionNed();
    const float altitude_m = -pos.z();

    if (_land_detected->landed()) {
      if (!_completed) {
        _completed = true;
        publishState("landed", altitude_m);
        completed(px4_ros2::Result::Success);
      }
      return;
    }

    if (!_touchdown && altitude_m <= _target_altitude_m) {
      _touchdown = true;
      _touchdown_xy = pos.head<2>();
      RCLCPP_INFO(_node.get_logger(), "%.1f m: policy released, touching down at %.2f m/s",
                  altitude_m, _touchdown_speed_m_s);
      if (_hizli_son_irtifa_m >= 0.0) {
        RCLCPP_INFO(_node.get_logger(), "  faster down to %.1f m: %.2f m/s (amendment 23)",
                    _hizli_son_irtifa_m, _hizli_son_hiz_m_s);
      }
    }

    if (_touchdown) {
      const bool hizli = _hizli_son_irtifa_m >= 0.0 && altitude_m > _hizli_son_irtifa_m;
      px4_ros2::TrajectorySetpoint sp;
      sp.withPositionX(_touchdown_xy.x())
          .withPositionY(_touchdown_xy.y())
          .withVelocityZ(static_cast<float>(hizli ? _hizli_son_hiz_m_s : _touchdown_speed_m_s))
          .withYaw(_heading);
      _trajectory->update(sp);
      publishState("touchdown", altitude_m);
      return;
    }

    const bool fresh = _have_command &&
                       (_node.now() - _command_time).seconds() <= _command_timeout_s;
    _trajectory->update(fresh ? _command : Eigen::Vector3f::Zero(), {}, _heading);
    publishState(fresh ? "following" : "hold (no fresh command)", altitude_m);
  }

 private:
  void requestActivation()
  {
    px4_msgs::msg::VehicleCommand cmd{};
    cmd.timestamp = static_cast<uint64_t>(_node.now().nanoseconds() / 1000);
    cmd.command = 100001;  // VEHICLE_CMD_SET_NAV_STATE, as run_sim.sh uses for Emergency Landing
    cmd.param1 = static_cast<float>(id());
    cmd.target_system = 1;
    cmd.target_component = 1;
    cmd.source_system = 255;
    cmd.source_component = 190;
    cmd.from_external = true;
    _vehicle_command_pub->publish(cmd);
    RCLCPP_INFO(_node.get_logger(), "requested activation (nav_state %d)", static_cast<int>(id()));
  }

  void publishState(const std::string& what, float altitude_m)
  {
    const rclcpp::Time now = _node.now();
    if ((now - _last_state).seconds() < 0.5 && what == _last_what) {
      return;
    }
    _last_state = now;
    _last_what = what;
    std::ostringstream s;
    s.precision(3);
    s << what << " alt=" << altitude_m << " cmd_ned=(" << _command.x() << "," << _command.y() << ","
      << _command.z() << ")";
    std_msgs::msg::String m;
    m.data = s.str();
    _state_pub->publish(m);
  }

  rclcpp::Node& _node;
  std::shared_ptr<px4_ros2::TrajectorySetpointType> _trajectory;
  std::shared_ptr<px4_ros2::OdometryLocalPosition> _local_position;
  std::shared_ptr<px4_ros2::LandDetected> _land_detected;
  rclcpp::Subscription<geometry_msgs::msg::TwistStamped>::SharedPtr _command_sub;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr _activate_sub;
  rclcpp::Publisher<px4_msgs::msg::VehicleCommand>::SharedPtr _vehicle_command_pub;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr _state_pub;

  double _target_altitude_m{5.0};
  double _touchdown_speed_m_s{0.7};
  double _command_timeout_s{0.5};
  double _hizli_son_irtifa_m{-1.0};
  double _hizli_son_hiz_m_s{2.0};
  Eigen::Vector3f _command{Eigen::Vector3f::Zero()};
  rclcpp::Time _command_time{0, 0, RCL_ROS_TIME};
  rclcpp::Time _last_state{0, 0, RCL_ROS_TIME};
  std::string _last_what;
  bool _have_command{false};
  bool _touchdown{false};
  bool _completed{false};
  float _heading{0.f};
  Eigen::Vector2f _touchdown_xy{Eigen::Vector2f::Zero()};
};

}  // namespace eland_rl
