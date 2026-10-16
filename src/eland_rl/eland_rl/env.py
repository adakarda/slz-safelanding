"""Gymnasium environment for the RL emergency landing study.

Everything here is fixed by docs/onkayit/rl_f0_onkayit.md; the section numbers
below point into it. The method is Bartolomei et al., IROS 2022: a policy that
sees a 128x128 semantic + depth image and picks one of ten high-level actions
every 0.25 s, PX4 doing the flying.

ACTIONS (2.3), body frame, heading held:
    0      halt
    1..8   lateral, 1 m/s, towards 0, 45, ..., 315 deg from the nose
           (1 = nose = image up, 3 = left, 5 = back, 7 = right)
    9      descend, 2 m/s

REWARD (3), R = w_t R_t + w_S R_S + w_C R_C + w_A R_A + R_T:
    R_t  -0.2 per step, 0 on the terminal step
    R_S  sum over classes of w_s * pixel share; w_s = +1 safe, -1 otherwise
    R_C  0 beyond d* = 3 m, -1 / (d_min - r) inside it (r = 0.5 m)
    R_A  lateral -0.05, halt -0.5, descend +1
    R_T  +50 safe landing, -20 unsafe landing, -20 collision, -50 time out,
         -5 out of bounds

AN EPISODE ENDS (2.5) when the camera reaches 5 m (success if the class
holding the most pixels of the full view is a safe one), when it leaves the
scene, on collision, or at max_t. There is no early stop on a 90 % view.
"""
import math
from dataclasses import dataclass, field

import gymnasium as gym
import numpy as np

from eland_common import classes

from .camera import Camera
from .dynamics import DynamicsParams, Vehicle

N_CLASSES = 8                       # seven taxonomy classes + UNKNOWN


@dataclass
class EnvConfig:
    step_s: float = 0.25
    v_lateral: float = 1.0
    v_descend: float = 2.0
    target_h: float = 5.0
    max_t: float = 90.0             # training; tests use 30 s
    start_h: tuple = (20.0, 30.0)
    min_inside: float = 0.7         # share of the first view that must be on the photo
    random_yaw: bool = True         # heading drawn per episode, held within it
    safe_classes: tuple = tuple(classes.DEFAULT_SAFE_CLASSES)
    binary: bool = False            # ablation: semantic channel is safe / not safe
    w_t: float = 1.0
    w_s: float = 1.0
    w_c: float = 0.5
    w_a: float = 1.0
    r_step: float = -0.2
    sem_good: float = 1.0
    sem_bad: float = -1.0
    a_lateral: float = -0.05
    a_halt: float = -0.5
    a_descend: float = 1.0
    land_good: float = 50.0
    land_bad: float = -20.0
    collision: float = -20.0
    timeout: float = -50.0
    out_of_bounds: float = -5.0
    d_star: float = 3.0
    robot_r: float = 0.5
    depth_norm_m: float = 40.0
    sora_m: float = 3.0
    image_size: int = 128
    dynamics: DynamicsParams = field(default_factory=DynamicsParams)
    randomise_dynamics: bool = True


class LandingEnv(gym.Env):
    metadata = {'render_modes': []}

    def __init__(self, scenes, config=None):
        super().__init__()
        if not scenes:
            raise ValueError('at least one scene is needed')
        self.scenes = list(scenes)
        self.cfg = config or EnvConfig()
        self.cam = Camera(self.cfg.image_size)
        n = self.cfg.image_size
        self.observation_space = gym.spaces.Box(0.0, 1.0, (2, n, n), np.float32)
        self.action_space = gym.spaces.Discrete(10)
        ang = np.radians(np.arange(8) * 45.0)
        self._lateral = np.stack([np.cos(ang), np.sin(ang)], 1) * self.cfg.v_lateral
        self._safe = np.zeros(N_CLASSES, bool)
        self._safe[list(self.cfg.safe_classes)] = True
        self.scene = None
        self.veh = None
        self.steps = 0

    # ------------------------------------------------------------------ helpers
    def _v_cmd(self, a):
        if a == 9:
            return np.array([0.0, 0.0, -self.cfg.v_descend])
        if a == 0:
            return np.zeros(3)
        bx, by = self._lateral[a - 1]
        c, s = math.cos(self.veh.yaw), math.sin(self.veh.yaw)
        return np.array([c * bx - s * by, s * bx + c * by, 0.0])

    def _observe(self):
        pos, R = self.veh.delayed_pose()
        sem, depth = self.cam.semantic_depth(self.scene, pos, R)
        if self.cfg.binary:
            ch0 = self._safe[sem].astype(np.float32)
        else:
            ch0 = sem.astype(np.float32) / (N_CLASSES - 1)
        ch1 = np.clip(np.where(np.isfinite(depth), depth, self.cfg.depth_norm_m) / self.cfg.depth_norm_m, 0, 1)
        obs = np.stack([ch0, ch1.astype(np.float32)])
        return obs, sem, depth

    def _start(self, rng, options):
        cfg = self.cfg
        if options and 'start' in options:
            x, y, h, yaw = options['start']
            return np.array([x, y, h], float), float(yaw)
        hx, hy = self.scene.half
        yaw = rng.uniform(0, 2 * math.pi) if cfg.random_yaw else 0.0
        level = Vehicle(DynamicsParams(), (0, 0, 1), yaw).attitude()
        best = None
        for _ in range(200):
            p = np.array([rng.uniform(-hx, hx), rng.uniform(-hy, hy), rng.uniform(*cfg.start_h)])
            f = self.cam.inside_fraction(self.scene, p, level)
            if f >= cfg.min_inside:
                return p, yaw
            if best is None or f > best[0]:
                best = (f, p)
        return best[1], yaw

    # --------------------------------------------------------------- gym API
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        rng = self.np_random
        if options and 'scene_index' in options:
            self.scene = self.scenes[options['scene_index']]
        else:
            self.scene = self.scenes[rng.integers(len(self.scenes))]
        params = self.cfg.dynamics
        if options and 'dynamics' in options:
            params = options['dynamics']
        elif self.cfg.randomise_dynamics:
            params = params.randomised(rng)
        pos, yaw = self._start(rng, options)
        self.veh = Vehicle(params, pos, yaw)
        self.steps = 0
        obs, _, _ = self._observe()
        info = {'scene': self.scene.name, 'start': (*pos, yaw),
                'dynamics': params}
        return obs, info

    def step(self, action):
        cfg = self.cfg
        a = int(action)
        self.veh.step(self._v_cmd(a), cfg.step_s)
        self.steps += 1
        pos = self.veh.pos
        obs, sem, depth = self._observe()

        safe_share = float(self._safe[sem].mean())
        r_s = cfg.sem_good * safe_share + cfg.sem_bad * (1.0 - safe_share)
        d_min = float(np.min(depth))
        r_c = 0.0
        if cfg.robot_r < d_min < cfg.d_star:
            r_c = -1.0 / (d_min - cfg.robot_r)
        r_a = cfg.a_descend if a == 9 else (cfg.a_halt if a == 0 else cfg.a_lateral)

        outcome, r_t_end = None, 0.0
        if not self.scene.inside(pos[0], pos[1]):
            outcome, r_t_end = 'out_of_bounds', cfg.out_of_bounds
        elif d_min <= cfg.robot_r:
            outcome, r_t_end = 'collision', cfg.collision
        elif pos[2] <= cfg.target_h:
            now, _ = self.cam.semantic_depth(self.scene, pos, self.veh.attitude())
            majority = int(np.bincount(now.ravel(), minlength=N_CLASSES).argmax())
            ok = bool(self._safe[majority])
            outcome = 'safe_landing' if ok else 'unsafe_landing'
            r_t_end = cfg.land_good if ok else cfg.land_bad
        elif self.veh.t >= cfg.max_t - 1e-9:
            outcome, r_t_end = 'timeout', cfg.timeout

        done = outcome is not None
        r_t = 0.0 if done else cfg.r_step
        reward = cfg.w_t * r_t + cfg.w_s * r_s + cfg.w_c * r_c + cfg.w_a * r_a + r_t_end
        info = {'r_s': r_s, 'r_c': r_c, 'r_a': r_a}
        if done:
            sora = self.scene.hazard_distance(pos[0], pos[1])
            info.update(outcome=outcome, success=outcome == 'safe_landing', t=self.veh.t,
                        landing_xy=(float(pos[0]), float(pos[1])), sora_distance_m=sora,
                        sora_ok=bool(outcome == 'safe_landing' and sora >= cfg.sora_m))
        return obs, float(reward), done, False, info
