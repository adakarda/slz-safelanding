"""Amendment 23: faster final descent in the RL Landing mode, and the switches to reach it (all default off).

  eland_rl_mode: parameters hizli_son_irtifa_m (default -1 = off) and hizli_son_hiz_m_s (2.0). When on, the
    touchdown phase (below target_altitude_m, 5 m) descends at hizli_son_hiz_m_s down to hizli_son_irtifa_m and at
    touchdown_speed_m_s (0.7) below it. Off: the old single speed, unchanged.
  run_airsim.sh: --hizli-son METRE passes hizli_son_irtifa_m to the mode.
  inis_sina.sh:  --hizli-son METRE passed through to run_airsim.sh (label suffix _hs<METRE>).

    python3 yama_rl_mod.py
"""
import os

W = os.path.expanduser('~/ros2_ws/src')


def yama(yol, eski, yeni):
    s = open(yol, encoding='utf-8').read()
    if yeni in s:
        print('zaten var:', os.path.basename(yol)); return
    assert s.count(eski) == 1, (yol, eski)
    open(yol, 'w', encoding='utf-8').write(s.replace(eski, yeni))
    print('yamandi:', os.path.basename(yol))


h = f'{W}/eland_rl_mode/include/rl_landing_mode.hpp'
yama(h, '    _command_timeout_s = node.declare_parameter<double>("command_timeout_s", 0.5);\n',
     '    _command_timeout_s = node.declare_parameter<double>("command_timeout_s", 0.5);\n'
     '    // amendment 23: faster touchdown phase down to hizli_son_irtifa_m; < 0 (default) keeps the single speed\n'
     '    _hizli_son_irtifa_m = node.declare_parameter<double>("hizli_son_irtifa_m", -1.0);\n'
     '    _hizli_son_hiz_m_s = node.declare_parameter<double>("hizli_son_hiz_m_s", 2.0);\n')
yama(h, '    if (_touchdown) {\n'
        '      px4_ros2::TrajectorySetpoint sp;\n'
        '      sp.withPositionX(_touchdown_xy.x())\n'
        '          .withPositionY(_touchdown_xy.y())\n'
        '          .withVelocityZ(static_cast<float>(_touchdown_speed_m_s))\n',
     '    if (_touchdown) {\n'
     '      const bool hizli = _hizli_son_irtifa_m >= 0.0 && altitude_m > _hizli_son_irtifa_m;\n'
     '      px4_ros2::TrajectorySetpoint sp;\n'
     '      sp.withPositionX(_touchdown_xy.x())\n'
     '          .withPositionY(_touchdown_xy.y())\n'
     '          .withVelocityZ(static_cast<float>(hizli ? _hizli_son_hiz_m_s : _touchdown_speed_m_s))\n')
yama(h, '  double _command_timeout_s{0.5};\n',
     '  double _command_timeout_s{0.5};\n'
     '  double _hizli_son_irtifa_m{-1.0};\n'
     '  double _hizli_son_hiz_m_s{2.0};\n')
yama(h, '      RCLCPP_INFO(_node.get_logger(), "%.1f m: policy released, touching down at %.2f m/s",\n'
        '                  altitude_m, _touchdown_speed_m_s);\n',
     '      RCLCPP_INFO(_node.get_logger(), "%.1f m: policy released, touching down at %.2f m/s",\n'
     '                  altitude_m, _touchdown_speed_m_s);\n'
     '      if (_hizli_son_irtifa_m >= 0.0) {\n'
     '        RCLCPP_INFO(_node.get_logger(), "  faster down to %.1f m: %.2f m/s (amendment 23)",\n'
     '                    _hizli_son_irtifa_m, _hizli_son_hiz_m_s);\n'
     '      }\n')

r = f'{W}/eland_airsim/scripts/run_airsim.sh'
yama(r, '\t--havada) HAVADA=$2; shift ;;\n',
     '\t--havada) HAVADA=$2; shift ;;\n'
     '\t--hizli-son) HIZLI_SON=$2; shift ;;\n')
yama(r, 'IZLE=0; HAVADA=""\n', 'IZLE=0; HAVADA=""; HIZLI_SON=""\n')
yama(r, '\t\tros2 run eland_rl_mode rl_landing_mode >"$LOG_DIR/rl_mod.log" 2>&1 &\n',
     '\t\tros2 run eland_rl_mode rl_landing_mode \\\n'
     '\t\t\t${HIZLI_SON:+--ros-args -p hizli_son_irtifa_m:=$HIZLI_SON} >"$LOG_DIR/rl_mod.log" 2>&1 &\n')
yama(r, '#   --havada N,E,IRTIFA | rastgele[:TOHUM]\n',
     '#   --hizli-son METRE   RL modu 5 m\'nin altinda METRE\'ye kadar 2 m/s, sonra 0.7 m/s iner (Duzeltme 23; yoksa\n'
     '#                tek hiz 0.7 m/s, eskisi gibi)\n'
     '#   --havada N,E,IRTIFA | rastgele[:TOHUM]\n')

i = f'{W}/eland_airsim/scripts/inis_sina.sh'
yama(i, '\t--kalkan) RL+=(--kalkan "$2"); RL_AD="${RL_AD}_k$2"; shift ;;\n',
     '\t--kalkan) RL+=(--kalkan "$2"); RL_AD="${RL_AD}_k$2"; shift ;;\n'
     '\t--hizli-son) RL+=(--hizli-son "$2"); RL_AD="${RL_AD}_hs$2"; shift ;;\n')
