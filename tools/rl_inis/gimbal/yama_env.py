"""Amendment 25: gimbal camera in the light environment (default off) and the evaluation's locking shield using it.

  env.py: EnvConfig.gimbal (False). On: the camera stays level, only its heading turns with the vehicle (a
    stabilised gimbal); the image is taken from the delayed position with that level attitude. LandingEnv.kamera_pozu()
    returns the camera pose the observation uses; _observe and the landing view use it. Off: the delayed body pose and
    the body attitude, as before.
  evaluate.py: rl_kalkan2 projects its target with env.kamera_pozu() (the same pose as delayed_pose() when off).

    python3 yama_env.py ENV.py EVALUATE.py
"""
import sys

env_p, ev_p = sys.argv[1], sys.argv[2]


def yama(p, pairs):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if new in s:
            continue
        assert s.count(old) == 1, (p, old)
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)
    print('yamandi:', p)


yama(env_p, [
    ("from .camera import Camera, ground_hits, sora_channel\n",
     "from .camera import Camera, ground_hits, rotation, sora_channel\n"),
    ("    kanallar: tuple = ()\n",
     "    kanallar: tuple = ()\n"
     "    # Amendment 25: the camera on a stabilised gimbal, level, its heading turning with the vehicle\n"
     "    gimbal: bool = False\n"),
    ("    def _observe(self):\n"
     "        cfg, sc = self.cfg, self.scene\n"
     "        pos, R = self.veh.delayed_pose()\n",
     "    def kamera_pozu(self):\n"
     "        \"\"\"(position, attitude) of the camera image arriving now: the delayed body pose, or with cfg.gimbal the\n"
     "        same position with a level attitude at the vehicle's heading (amendment 25).\"\"\"\n"
     "        pos, R = self.veh.delayed_pose()\n"
     "        if self.cfg.gimbal:\n"
     "            R = rotation((0.0, 0.0, 1.0), self.veh.yaw)\n"
     "        return pos, R\n"
     "\n"
     "    def _observe(self):\n"
     "        cfg, sc = self.cfg, self.scene\n"
     "        pos, R = self.kamera_pozu()\n"),
    ("            now, _ = self.cam.semantic_depth(self.scene, pos, self.veh.attitude())\n",
     "            now, _ = self.cam.semantic_depth(self.scene, pos, rotation((0.0, 0.0, 1.0), self.veh.yaw)\n"
     "                                             if self.cfg.gimbal else self.veh.attitude())\n"),
])
yama(ev_p, [
    ("                    pos, R = env.veh.delayed_pose()\n"
     "                    return kk(rl(o), o, pos[2], env.veh.t, pos, R, env.veh.pos[:2], env.veh.yaw, env.cam.rays)[0]\n",
     "                    pos, R = env.kamera_pozu()      # amendment 25: the gimbal's level pose when cfg.gimbal\n"
     "                    return kk(rl(o), o, pos[2], env.veh.t, pos, R, env.veh.pos[:2], env.veh.yaw, env.cam.rays)[0]\n"),
])
