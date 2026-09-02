/****************************************************************************
 * Emergency Landing -- a PX4 flight mode registered from ROS 2.
 *
 * Consumes landing candidates from the perception pipeline and flies the
 * vehicle down onto the best one.
 *
 * WHY A REGISTERED MODE AND NOT AN OFFBOARD SCRIPT
 *
 * The reference pipeline in ~/ws_slz drove the vehicle by streaming
 * OffboardControlMode heartbeats and hand-rolled VehicleCommand arming. That
 * works in a demo and fails everywhere else: the behaviour never appears in
 * QGroundControl, PX4's failsafe state machine knows nothing about it, and if
 * the ROS process dies the vehicle sits in offboard until COM_OF_LOSS_T
 * expires. A mode registered through px4_ros2 is a first-class PX4 mode: it
 * shows up in the GCS mode list, it participates in health and arming checks,
 * and PX4 falls back to an internal mode on its own if this process goes away
 * -- measured: killing this node switched nav_state 23 -> 5 (AUTO_RTL).
 *
 * WHERE THE LANDING POLICY LIVES -- NOT HERE
 *
 * This class never sees a semantic class ID. It receives a LandingCandidate
 * that is already a metric point with a clearance radius and a risk score, and
 * its only judgement is "is this candidate recent enough to still trust". What
 * counts as landable under SORA -- which surfaces, and the rule that a person
 * or a vehicle rules out a site regardless of how flat it is -- is entirely in
 * detector_node's class_risk table. Keep it that way: a second opinion about
 * safety in the control layer is a second place to get it wrong.
 *
 * FRAMES
 *
 * The perception chain is ENU throughout (east, north, up). PX4 is NED (north,
 * east, down). The conversion happens in candidateNed() and nowhere else.
 ****************************************************************************/
#pragma once

#include <Eigen/Core>
#include <eland_msgs/msg/landing_candidate.hpp>
#include <eland_msgs/msg/landing_state.hpp>
#include <px4_ros2/components/mode.hpp>
#include <px4_ros2/control/setpoint_types/experimental/trajectory.hpp>
#include <px4_ros2/control/setpoint_types/multicopter/goto.hpp>
#include <px4_ros2/odometry/local_position.hpp>
#include <px4_ros2/vehicle_state/land_detected.hpp>
#include <rclcpp/rclcpp.hpp>

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>

namespace eland {

/// Name shown in the GCS mode list. QGroundControl Daily picks up dynamically
/// registered modes; a stable release may not refresh the list.
static const std::string kModeName = "Emergency Landing";

class EmergencyLandingMode : public px4_ros2::ModeBase {
 public:
  /// Mirrors the constants in eland_msgs/msg/LandingState.msg.
  enum class State {
    Search = eland_msgs::msg::LandingState::SEARCH,
    Approach = eland_msgs::msg::LandingState::APPROACH,
    Validate = eland_msgs::msg::LandingState::VALIDATE,
    Hold = eland_msgs::msg::LandingState::HOLD,
    Abort = eland_msgs::msg::LandingState::ABORT,
    Commit = eland_msgs::msg::LandingState::COMMIT,
  };

  /// Build the registration settings, including which PX4 internal mode this
  /// one takes over.
  ///
  /// Replacing an internal mode is how the "link lost" scenario becomes real
  /// rather than a button someone presses. PX4's manual-control-loss failsafe
  /// picks its action from NAV_RCL_ACT, whose options are Hold(1),
  /// Return(2, default), Land(3), Terminate(5), Disarm(6). Note what is NOT
  /// in that list: Descend. Descend is only reached as a fallback when the
  /// position estimate is gone, which is a situation this mode cannot work in
  /// anyway -- so replacing Descend, which an earlier draft of the plan
  /// proposed, would have produced a mode that never triggers on link loss.
  ///
  /// Default is Return, because that is both what the project brief specifies
  /// and PX4's default failsafe action, so link loss reaches this mode with no
  /// parameter changes at all. The tradeoff is real and worth knowing: while
  /// this is registered, an operator pressing RTL also gets an emergency
  /// landing here rather than a flight home. Set `replace_internal_mode` to
  /// "land" (with NAV_RCL_ACT=3) or "none" if that is not wanted.
  static Settings makeSettings(rclcpp::Node& node)
  {
    const std::string target =
        node.declare_parameter<std::string>("replace_internal_mode", "rtl");
    Settings settings{kModeName};
    if (target == "rtl") {
      settings.replaceInternalMode(ModeBase::kModeIDRtl);
    } else if (target == "land") {
      settings.replaceInternalMode(ModeBase::kModeIDLand);
    } else if (target == "descend") {
      settings.replaceInternalMode(ModeBase::kModeIDDescend);
    } else if (target != "none") {
      RCLCPP_WARN(node.get_logger(),
                  "unknown replace_internal_mode \"%s\"; registering as a "
                  "standalone mode. Valid: rtl, land, descend, none",
                  target.c_str());
    }
    return settings;
  }

  explicit EmergencyLandingMode(rclcpp::Node& node)
      : ModeBase(node, makeSettings(node)), _node(node)
  {
    _goto_setpoint = std::make_shared<px4_ros2::MulticopterGotoSetpointType>(*this);
    // Touchdown needs a velocity setpoint rather than a position one; see the
    // COMMIT branch of updateSetpoint() for why.
    _trajectory_setpoint = std::make_shared<px4_ros2::TrajectorySetpointType>(*this);
    _local_position = std::make_shared<px4_ros2::OdometryLocalPosition>(*this);
    _land_detected = std::make_shared<px4_ros2::LandDetected>(*this);

    declareParameters();

    // DECISION_QOS on the Python side: reliable, volatile, keep-last 10.
    // Candidates must not be silently dropped -- a missed candidate reads as
    // "perception went quiet", which pushes the machine towards HOLD/ABORT.
    const rclcpp::QoS decision_qos = rclcpp::QoS(10).reliable();

    _candidate_sub = _node.create_subscription<eland_msgs::msg::LandingCandidate>(
        _candidate_topic, decision_qos,
        [this](eland_msgs::msg::LandingCandidate::UniquePtr msg) {
          onCandidate(std::move(msg));
        });
    _state_pub =
        _node.create_publisher<eland_msgs::msg::LandingState>(_state_topic, decision_qos);
  }

  // ------------------------------------------------------------------
  void onActivate() override
  {
    _state = State::Search;
    _reason = "activated";
    _candidate_valid = false;
    _ever_had_candidate = false;
    _have_frozen_target = false;
    _completed = false;
    _attempts = 0;
    _search_time_s = 0.f;
    _commit_is_blind = false;
    // id() is the nav_state PX4 assigned at registration -- 23..30, i.e.
    // NAVIGATION_STATE_EXTERNAL1..8. Worth logging: it is the number you need
    // to drive the mode without a GCS, via
    // VehicleCommand::VEHICLE_CMD_SET_NAV_STATE with param1 = id().
    RCLCPP_INFO(_node.get_logger(), "%s activated (mode id / nav_state = %d)",
                kModeName.c_str(), static_cast<int>(id()));
  }

  void onDeactivate() override
  {
    RCLCPP_INFO(_node.get_logger(), "%s deactivated in state %s", kModeName.c_str(),
                stateName(_state));
  }

  // ------------------------------------------------------------------
  void updateSetpoint(float dt_s) override
  {
    if (!_local_position->positionXYValid() || !_local_position->positionZValid()) {
      _reason = "waiting for a valid local position estimate";
      publishState(0.f);
      return;  // publish no setpoint; PX4 holds
    }

    const Eigen::Vector3f pos_ned = _local_position->positionNed();
    _last_pos_ned = pos_ned;  // transition() needs it to freeze a commit target
    const float altitude_m = -pos_ned.z();
    const bool live = candidateIsLive();

    // Target in NED plus the vertical speed cap applied to it. Filled by the
    // state handlers below, published once at the end so there is exactly one
    // setpoint per update no matter which branch ran.
    Eigen::Vector3f target_ned = pos_ned;
    float max_vertical_speed = _descent_max_mps;

    switch (_state) {
      case State::Search: {
        // Loiter at search altitude until perception offers something.
        target_ned = {pos_ned.x(), pos_ned.y(), -_search_altitude_m};
        _search_time_s += dt_s;
        if (live) {
          transition(State::Approach, "candidate #" + std::to_string(_candidate.candidate_id) +
                                          " accepted, r=" + toStr(_candidate.radius) + " m");
        } else if (_search_timeout_s > 0.f && _search_time_s > _search_timeout_s) {
          // Out of search time. Coming down on an unverified site is a bad
          // outcome; staying airborne until the battery decides for us is a
          // worse one, and it is the outcome the old code guaranteed. Descend
          // -- onto the last site perception liked if there was one, straight
          // down otherwise, which is what PX4's own Descend failsafe does.
          transition(State::Commit,
                     _ever_had_candidate
                         ? "search timed out after " + toStr(_search_time_s) +
                               " s; committing to the last accepted candidate"
                         : "search timed out after " + toStr(_search_time_s) +
                               " s with no candidate ever found; DESCENDING BLIND");
        } else {
          _reason = "no valid candidate; loitering at search altitude (" +
                    toStr(_search_time_s) + "/" + toStr(_search_timeout_s) + " s)";
        }
      } break;

      case State::Approach: {
        if (!live) {
          transition(State::Search, "candidate lost during approach");
          break;
        }
        // Travel at the current altitude; descending before arriving would
        // shrink the camera footprint and starve the detector of context.
        const Eigen::Vector3f cand = candidateNed();
        target_ned = {cand.x(), cand.y(), pos_ned.z()};
        const float dist = horizontalDistance(pos_ned, cand);
        if (dist <= _arrival_radius_m) {
          transition(State::Validate, "reached candidate, " + toStr(dist) + " m error");
        } else {
          _reason = "approaching, " + toStr(dist) + " m to go";
        }
      } break;

      case State::Validate: {
        if (altitude_m <= _landing_altitude_m) {
          transition(State::Commit,
                     "at " + toStr(altitude_m) + " m, committing to touchdown");
          break;
        }
        if (!live) {
          // Below min_radius_altitude the camera no longer sees enough ground
          // to re-acquire, so freezing in place beats flying on blind. HOLD is
          // not yet a failed attempt -- the candidate may still come back.
          if (altitude_m < _min_radius_altitude_m) {
            transition(State::Hold, "candidate lost at " + toStr(altitude_m) +
                                        " m, too low to re-acquire");
          } else {
            // This one *is* a failed attempt: a descent was started and
            // given up on. Counting only the HOLD -> ABORT path would leave
            // VALIDATE <-> SEARCH free to oscillate forever, which is the
            // same unbounded loop wearing a different set of state names.
            abandonDescent(State::Search, "candidate lost at " + toStr(altitude_m) + " m");
          }
          break;
        }
        const Eigen::Vector3f cand = candidateNed();
        target_ned = {cand.x(), cand.y(), -_landing_altitude_m};
        max_vertical_speed = descentSpeed(altitude_m);
        _reason = "descending at <=" + toStr(max_vertical_speed) + " m/s [" +
                  std::string(_view_bounded ? "area" : "altitude") + "], region " +
                  toStr(_area_m2) + " m2 filling " + toStr(_area_ratio * 100.f) +
                  "% of view, alt " + toStr(altitude_m) + " m";
      } break;

      case State::Hold: {
        if (!_have_frozen_target) {
          _frozen_target_ned = pos_ned;
          _have_frozen_target = true;
        }
        target_ned = _frozen_target_ned;
        const float held_s = (_node.get_clock()->now() - _hold_start).seconds();
        if (live) {
          transition(State::Validate,
                     "candidate recovered after " + toStr(held_s) + " s hold");
        } else if (held_s > _hold_duration_s) {
          abandonDescent(State::Abort,
                         "hold exceeded " + toStr(_hold_duration_s) + " s");
        } else {
          _reason = "frozen, " + toStr(held_s) + "/" + toStr(_hold_duration_s) +
                    " s waiting for a candidate";
        }
      } break;

      case State::Abort: {
        target_ned = {pos_ned.x(), pos_ned.y(), -_search_altitude_m};
        if (altitude_m >= _search_altitude_m - _altitude_tolerance_m) {
          transition(State::Search, "climb complete at " + toStr(altitude_m) + " m");
        } else {
          _reason = "climbing back to search altitude, " + toStr(altitude_m) + " m";
        }
      } break;

      case State::Commit: {
        // Irreversible by design. A candidate that flickers out two metres off
        // the ground must not turn into a go-around: the vehicle is already
        // inside the footprint it validated, and climbing away costs more
        // energy than finishing.
        // completed() does not stop updateSetpoint() from being called: PX4
        // takes a few cycles to deactivate the mode, and at ~50 Hz that was
        // ten duplicate "touchdown" lines in the log. Latch it.
        if (_land_detected->landed()) {
          if (!_completed) {
            _completed = true;
            RCLCPP_INFO(_node.get_logger(), "touchdown detected, mode complete");
            _reason = "landed";
            publishState(altitude_m);
            completed(px4_ros2::Result::Success);
          }
          return;
        }

        // Touchdown is the one phase that must NOT be position-controlled in
        // the vertical axis. Commanding a goto target at ground level lands
        // the vehicle physically but leaves the position controller happily
        // holding hover thrust against a zero error, so PX4's land detector
        // never sees has_low_throttle and never reports `landed`. Measured:
        // altitude_agl 0.003 m, vz 0.003 m/s, has_low_throttle False,
        // landed False -- sitting on the ground, still armed, mode never
        // completing.
        //
        // Commanding a downward *velocity* instead is what PX4's own Land
        // mode does: the vehicle keeps being asked to descend after it has
        // run out of descent, thrust falls away, and the detector fires.
        // Horizontal position stays under position control so it does not
        // drift off the validated site while this happens.
        // The horizontal target was frozen on entering COMMIT, not recomputed
        // here. That matters for the blind-descent path: with no candidate
        // ever received, candidateNed() would read a default-constructed
        // message and fly the aircraft to the local origin instead of down.
        const float touchdown_speed = descentSpeed(altitude_m);
        px4_ros2::TrajectorySetpoint touchdown;
        touchdown.withPositionX(_commit_target_ned.x())
            .withPositionY(_commit_target_ned.y())
            .withVelocityZ(touchdown_speed);  // NED: down is positive
        _trajectory_setpoint->update(touchdown);

        _reason = std::string(_commit_is_blind ? "committed BLIND, " : "committed, ") +
                  "touching down at " + toStr(touchdown_speed) + " m/s";
        publishState(altitude_m);
        return;
      }
    }

    _goto_setpoint->update(target_ned, /*heading=*/{}, _max_horizontal_speed_mps,
                           max_vertical_speed);
    publishState(altitude_m);
  }

 private:
  // ------------------------------------------------------------------
  void declareParameters()
  {
    auto declare = [this](const std::string& name, double def) {
      return static_cast<float>(_node.declare_parameter<double>(name, def));
    };
    _search_altitude_m = declare("search_altitude", 15.0);
    _min_radius_altitude_m = declare("min_radius_altitude", 5.0);
    _landing_altitude_m = declare("landing_altitude", 2.0);
    _arrival_radius_m = declare("arrival_radius_m", 1.0);
    _altitude_tolerance_m = declare("altitude_tolerance_m", 0.5);
    _candidate_timeout_s = declare("candidate_timeout_s", 3.0);
    _hold_duration_s = declare("hold_duration_s", 5.0);
    _max_horizontal_speed_mps = declare("max_horizontal_speed", 3.0);

    // Two bounds on giving up. Both exist because the state machine, left to
    // itself, has no way to stop trying -- and a mode that is willing to
    // circle until the battery runs out has not made the situation better
    // than the emergency it was invoked for. Set either to <= 0 to disable it
    // and get the old unbounded behaviour back.
    _max_landing_attempts = _node.declare_parameter<int>("max_landing_attempts", 3);
    _search_timeout_s = declare("search_timeout_s", 60.0);

    // Descent law. See descentSpeed() for the reasoning behind the shape.
    _descent_size_gain = declare("descent_size_gain", 0.20);
    _descent_min_mps = declare("descent_min_mps", 0.3);
    _descent_max_mps = declare("descent_max_mps", 2.0);
    // Fallback only: used when no area measurement is available yet.
    _descent_altitude_gain = declare("descent_altitude_gain", 0.35);

    _candidate_topic = _node.declare_parameter<std::string>("candidate_topic", "/eland/candidate");
    _state_topic = _node.declare_parameter<std::string>("state_topic", "/eland/state");
  }

  /// Descent speed from the visual size of the landing site.
  ///
  /// The control variable is `area_ratio`: how much of the camera's field of
  /// view the chosen safe region fills. It rises as the aircraft descends, so
  /// the vehicle slows as it closes in -- and because it is measured in image
  /// space it needs no altitude estimate at all, which is what makes it hold
  /// up over sloped or raised ground where an AGL number would be wrong.
  ///
  /// The ratio alone is not enough, though. It conflates "how close am I" with
  /// "how big is the site": at 5 m a 10 m pad fills ~95% of the view while a
  /// 4 m pad fills ~15%, so a ratio-only law descends fastest onto the site
  /// with the least room for error. The fix is to let the site's own size set
  /// the ceiling, and let the ratio move the speed within it:
  ///
  ///     v_ceiling = clamp(k_size * sqrt(area), v_min, v_max)
  ///     v         = clamp(v_ceiling * (1 - area_ratio), v_min, v_ceiling)
  ///
  /// At 15 m that gives ~1.79 m/s toward a 10 m pad and ~0.79 m/s toward a 4 m
  /// pad: the small pad is approached more carefully at every altitude, not
  /// only at the end.
  ///
  /// The ratio is only used when the region is fully enclosed by the frame.
  /// A ratio near 1.0 is ambiguous otherwise -- "nearly touching down" and
  /// "the field is enormous" look identical -- and over open grassland the
  /// ambiguity is not academic: measured, area_ratio sat at 0.81 from 20 m
  /// down and the ratio-only law crawled the entire descent at the 0.3 m/s
  /// floor, 73 s instead of 27 s, never slowing near the ground because there
  /// was nothing left to slow from. When the region runs off the edge, fall
  /// back to altitude for proximity but keep the size-derived ceiling, which
  /// is still meaningful.
  /// Not const: it records what it decided, so publishState() can report the
  /// numbers the controller actually used rather than the HUD re-deriving
  /// them and drifting out of step.
  float descentSpeed(float altitude_m)
  {
    if (!_have_area_measurement) {
      // No candidate measured yet. Fall back to the altitude law rather than
      // guessing a ratio -- a wrong ratio would command a wrong speed, while
      // this is merely a cruder speed.
      _area_law_active = false;
      _last_ceiling_mps = _descent_max_mps;
      _last_commanded_mps = std::clamp(_descent_altitude_gain * altitude_m,
                                       _descent_min_mps, _descent_max_mps);
      return _last_commanded_mps;
    }
    const float ceiling = std::clamp(_descent_size_gain * std::sqrt(_area_m2),
                                     _descent_min_mps, _descent_max_mps);
    _last_ceiling_mps = ceiling;
    if (!_view_bounded) {
      _area_law_active = false;
      _last_commanded_mps =
          std::clamp(_descent_altitude_gain * altitude_m, _descent_min_mps, ceiling);
      return _last_commanded_mps;
    }
    _area_law_active = true;
    const float ratio = std::clamp(_area_ratio, 0.f, 1.f);
    _last_commanded_mps = std::clamp(ceiling * (1.f - ratio), _descent_min_mps, ceiling);
    return _last_commanded_mps;
  }

  void onCandidate(eland_msgs::msg::LandingCandidate::UniquePtr msg)
  {
    if (_state == State::Commit) {
      return;  // COMMIT ignores everything that arrives after it
    }
    _last_candidate_time = _node.get_clock()->now();
    _candidate_valid = msg->valid;
    if (msg->valid) {
      _candidate = *msg;
      _ever_had_candidate = true;
      // Latched separately from _candidate so COMMIT keeps steering on the
      // last good measurement after it stops accepting new candidates.
      _area_ratio = msg->area_ratio;
      _area_m2 = msg->area_m2;
      _view_bounded = msg->view_bounded;
      _have_area_measurement = msg->area_m2 > 0.f;
    }
  }

  bool candidateIsLive() const
  {
    if (!_candidate_valid || _last_candidate_time.nanoseconds() == 0) {
      return false;
    }
    return (_node.get_clock()->now() - _last_candidate_time).seconds() <= _candidate_timeout_s;
  }

  /// The one and only ENU -> NED conversion in the control path.
  /// LandingCandidate.position is ENU in the map frame: x east, y north, and
  /// z is always 0 (the detector works on a ground-plane grid).
  Eigen::Vector3f candidateNed() const
  {
    return {static_cast<float>(_candidate.position.y), static_cast<float>(_candidate.position.x),
            -static_cast<float>(_candidate.position.z)};
  }

  static float horizontalDistance(const Eigen::Vector3f& a, const Eigen::Vector3f& b)
  {
    return (a.head(2) - b.head(2)).norm();
  }

  /// Record one abandoned descent and decide whether another is affordable.
  ///
  /// Every path that gives up on a descent in progress goes through here, so
  /// the retry budget cannot be escaped by looping through a different pair of
  /// states. Climbing back to search altitude costs energy; repeating it
  /// without limit spends all of it and then the aircraft falls anyway, so
  /// past the budget the mode lands on the best site it has rather than the
  /// best site it wishes it had.
  void abandonDescent(State fallback, const std::string& reason)
  {
    ++_attempts;
    if (_max_landing_attempts > 0 && _attempts >= _max_landing_attempts) {
      transition(State::Commit, reason + "; attempt " + std::to_string(_attempts) +
                                    "/" + std::to_string(_max_landing_attempts) +
                                    ", no retries left, committing anyway");
      return;
    }
    transition(fallback, reason + " (attempt " + std::to_string(_attempts) + "/" +
                             std::to_string(_max_landing_attempts) + ")");
  }

  void transition(State next, const std::string& reason)
  {
    if (next == _state) {
      _reason = reason;
      return;
    }
    RCLCPP_INFO(_node.get_logger(), "%s -> %s: %s", stateName(_state), stateName(next),
                reason.c_str());
    _state = next;
    _reason = reason;
    if (next == State::Hold) {
      _hold_start = _node.get_clock()->now();
      _have_frozen_target = false;
    } else if (next == State::Commit) {
      // Freeze the touchdown point once, here. COMMIT is irreversible, so
      // there is nothing to gain from re-reading a candidate it has already
      // decided to ignore -- and if there is no candidate at all, the only
      // sane horizontal target is where the aircraft already is.
      _commit_is_blind = !_ever_had_candidate;
      _commit_target_ned = _commit_is_blind ? _last_pos_ned : candidateNed();
      if (_commit_is_blind) {
        RCLCPP_WARN(_node.get_logger(),
                    "committing to a blind descent at the current position -- "
                    "no landing site was ever accepted");
      }
    }
  }

  void publishState(float altitude_m)
  {
    // updateSetpoint runs at ~30 Hz; the state channel is for humans and logs,
    // so throttle it to something readable.
    const rclcpp::Time now = _node.get_clock()->now();
    if (_last_state_pub.nanoseconds() != 0 && (now - _last_state_pub).seconds() < 0.1) {
      return;
    }
    _last_state_pub = now;

    eland_msgs::msg::LandingState msg;
    msg.header.stamp = now;
    msg.header.frame_id = "map";
    msg.state = static_cast<uint8_t>(_state);
    msg.reason = _reason;
    msg.altitude_agl = altitude_m;
    msg.commanded_descent_mps = _last_commanded_mps;
    msg.descent_ceiling_mps = _last_ceiling_mps;
    msg.area_ratio = _area_ratio;
    msg.area_law_active = _area_law_active;
    _state_pub->publish(msg);
  }

  static const char* stateName(State s)
  {
    switch (s) {
      case State::Search:
        return "SEARCH";
      case State::Approach:
        return "APPROACH";
      case State::Validate:
        return "VALIDATE";
      case State::Hold:
        return "HOLD";
      case State::Abort:
        return "ABORT";
      case State::Commit:
        return "COMMIT";
    }
    return "?";
  }

  /// Short fixed-point float formatting for the reason strings.
  static std::string toStr(float v)
  {
    std::string s = std::to_string(v);
    const auto dot = s.find('.');
    if (dot != std::string::npos && s.size() > dot + 3) {
      s.resize(dot + 3);
    }
    return s;
  }

  // ------------------------------------------------------------------
  rclcpp::Node& _node;

  State _state{State::Search};
  std::string _reason{"startup"};

  eland_msgs::msg::LandingCandidate _candidate;
  bool _candidate_valid{false};
  rclcpp::Time _last_candidate_time{0, 0, RCL_ROS_TIME};
  rclcpp::Time _hold_start{0, 0, RCL_ROS_TIME};
  rclcpp::Time _last_state_pub{0, 0, RCL_ROS_TIME};

  Eigen::Vector3f _frozen_target_ned{0.f, 0.f, 0.f};
  bool _have_frozen_target{false};
  bool _completed{false};

  Eigen::Vector3f _last_pos_ned{0.f, 0.f, 0.f};
  Eigen::Vector3f _commit_target_ned{0.f, 0.f, 0.f};
  bool _commit_is_blind{false};
  bool _ever_had_candidate{false};
  int _attempts{0};
  float _search_time_s{0.f};

  float _search_altitude_m{15.f};
  float _min_radius_altitude_m{5.f};
  float _landing_altitude_m{2.f};
  float _arrival_radius_m{1.f};
  float _altitude_tolerance_m{0.5f};
  float _candidate_timeout_s{3.f};
  float _hold_duration_s{5.f};
  float _max_horizontal_speed_mps{3.f};
  int _max_landing_attempts{3};
  float _search_timeout_s{60.f};
  float _descent_size_gain{0.20f};
  float _descent_min_mps{0.3f};
  float _descent_max_mps{2.f};
  float _descent_altitude_gain{0.35f};
  float _area_ratio{0.f};
  float _area_m2{0.f};
  bool _view_bounded{false};
  bool _have_area_measurement{false};
  float _last_commanded_mps{0.f};
  float _last_ceiling_mps{0.f};
  bool _area_law_active{false};
  std::string _candidate_topic{"/eland/candidate"};
  std::string _state_topic{"/eland/state"};

  std::shared_ptr<px4_ros2::MulticopterGotoSetpointType> _goto_setpoint;
  std::shared_ptr<px4_ros2::TrajectorySetpointType> _trajectory_setpoint;
  std::shared_ptr<px4_ros2::OdometryLocalPosition> _local_position;
  std::shared_ptr<px4_ros2::LandDetected> _land_detected;
  rclcpp::Subscription<eland_msgs::msg::LandingCandidate>::SharedPtr _candidate_sub;
  rclcpp::Publisher<eland_msgs::msg::LandingState>::SharedPtr _state_pub;
};

}  // namespace eland
