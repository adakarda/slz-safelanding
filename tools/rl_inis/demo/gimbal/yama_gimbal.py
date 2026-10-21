"""Gimbal switch for the AirSim RL runs (Arda, 21.10: "segmentasyon kamerasi calisan gimball"), default off.

  run_airsim.sh --gimbal: the downward camera 'asagi' gets AirSim's gimbal stabilisation (pitch -90 and roll 0 held
    in the world frame, heading follows the vehicle), and policy_node gets gimbal:=true.
  policy_node gimbal (default false): the observation is built from a level camera with the vehicle's heading
    (the camera's real pose under the gimbal) instead of the body's tilted pose. The shield height, the command
    frame and the CSV log keep the body pose.

    python3 yama_gimbal.py
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


p = f'{W}/eland_rl/eland_rl/policy_node.py'
yama(p, "from .camera import Camera, ground_hits, nearest_source_index, sora_channel\n",
     "from .camera import Camera, ground_hits, nearest_source_index, rotation, sora_channel\n")
yama(p, "        p('kalkan_m', -1.0)\n",
     "        p('kalkan_m', -1.0)\n"
     "        p('gimbal', False)          # the camera on a stabilised gimbal: level, heading follows the vehicle\n")
yama(p, "        self.kalkan_m = float(g('kalkan_m'))\n",
     "        self.kalkan_m = float(g('kalkan_m'))\n"
     "        self.gimbal = bool(g('gimbal'))\n")
yama(p, "        c = p + R @ np.array([0.0, 0.0, self.cam_off])\n"
        "        c[2] -= self.ground_z\n"
        "        got = self.observe(c, R)\n",
     "        c = p + R @ np.array([0.0, 0.0, self.cam_off])\n"
     "        c[2] -= self.ground_z\n"
     "        Rk = rotation((0.0, 0.0, 1.0), math.atan2(R[1, 0], R[0, 0])) if self.gimbal else R\n"
     "        got = self.observe(c, Rk)\n")

r = f'{W}/eland_airsim/scripts/run_airsim.sh'
yama(r, '\t--hizli-son) HIZLI_SON=$2; shift ;;\n',
     '\t--hizli-son) HIZLI_SON=$2; shift ;;\n'
     '\t--gimbal) GIMBAL=1 ;;\n')
yama(r, 'IZLE=0; HAVADA=""; HIZLI_SON=""\n', 'IZLE=0; HAVADA=""; HIZLI_SON=""; GIMBAL=0\n')
yama(r, 'python3 - "$WS_DIR/src/eland_airsim/config/settings_px4.json" "$AIRSIM_DIR/settings_px4.json" "$GW" "$BASLANGIC" "$IZLE" <<\'PY\'\n',
     'python3 - "$WS_DIR/src/eland_airsim/config/settings_px4.json" "$AIRSIM_DIR/settings_px4.json" "$GW" "$BASLANGIC" "$IZLE" \\\n'
     '\t"$GIMBAL" <<\'PY\'\n')
yama(r, "json.dump(s, open(sys.argv[2], 'w'), indent=2)\nPY\n",
     "if sys.argv[6] == '1':   # --gimbal: pitch and roll held in the world frame, heading follows the vehicle\n"
     "    v['Cameras']['asagi']['Gimbal'] = {'Stabilization': 1.0, 'Pitch': -90.0, 'Roll': 0.0}\n"
     "json.dump(s, open(sys.argv[2], 'w'), indent=2)\nPY\n")
yama(r, '\t\t\t-p ground_z_m:=0.0 -p kalkan_m:="$KALKAN_F" -p log_csv:="$LOG_DIR/politika.csv"\n',
     '\t\t\t-p ground_z_m:=0.0 -p kalkan_m:="$KALKAN_F" -p log_csv:="$LOG_DIR/politika.csv" \\\n'
     '\t\t\t-p gimbal:=$([ "$GIMBAL" = 1 ] && echo true || echo false)\n')
yama(r, '#   --havada N,E,IRTIFA | rastgele[:TOHUM]\n',
     '#   --gimbal     asagi kamera AirSim gimbaliyla sabit (dik bakar, yon aracla doner); policy_node da buna gore\n'
     '#   --havada N,E,IRTIFA | rastgele[:TOHUM]\n')
