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

from .camera import Camera, ground_hits, sora_channel
from .pilots import shield
from .dynamics import DynamicsParams, Vehicle
from .scene import MirroredScene

N_CLASSES = 8                       # seven taxonomy classes + UNKNOWN

#: Amendment 9: terminal reward by the class landed on (taxonomy index; 7 = unknown / off the photo).
#: Soft ground over hard ground; hazards ordered as SORA ranks the harm, the worst below a time-out.
ZEMIN_REWARDS = {0: 50.0, 1: 30.0, 2: -40.0, 3: -60.0, 4: -70.0, 5: -90.0, 6: -100.0, 7: -50.0}


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
    # Our landing reward (docs/onkayit/rl_f0_onkayit.md, amendment 4). Defaults keep the paper's.
    success_rule: str = 'majority'  # 'majority' (paper: 5 m view) or 'sora' (point under the vehicle)
    shaping_k: float = 0.0          # potential -k * min(d to nearest SORA-safe point, shaping_dmax)
    shaping_dmax: float = 20.0
    gamma: float = 0.99             # discount the potential shaping is built with (= PPO gamma)
    image_size: int = 128
    obs_mode: str = 'sem_depth'     # or 'sem_depth_sora': + SORA-safe mask from the image (amendment 5)
    # Amendment 7: what the observation is built from. Reward and success always use the GT mask.
    sem_source: str = 'gt'          # 'gt' or 'pred' (the scene's v3 prediction mask)
    depth_mode: str = 'flat'        # 'flat' (ray length to the ground) or 'elev' (Depth Anything relative elevation)
    sora_elev_tau: float = -1.0     # >= 0: SORA channel also refuses pixels whose elevation exceeds it
    shield_m: float = -1.0          # >= 0: the SORA shield acts inside the environment (amendment 8)
    dynamics: DynamicsParams = field(default_factory=DynamicsParams)
    randomise_dynamics: bool = True
    # Amendment 9 ('zemin' rule): success is a landable class at the point under the vehicle with no
    # buffer class closer than buffer_m; the terminal reward is set by the class landed on.
    land_rewards: dict = field(default_factory=lambda: dict(ZEMIN_REWARDS))
    buffer_classes: tuple = (6, 5)  # person, vehicle-animal; most severe first
    buffer_m: float = 2.0
    sora_metric: bool = True        # also judge landings by the 3 m SORA rule (a metric; one grid per scene)
    mirror: bool = False            # each episode sees its scene mirrored with p = 0.5
    # Amendment 11 ('zemin_v2'): >= 0 makes the shaping head for soft ground, unless the nearest soft
    # target is more than soft_bias_m farther than the nearest landable one; < 0 keeps zemin_v1's shaping.
    soft_bias_m: float = -1.0
    soft_classes: tuple = (0,)


#: Reward presets. 'paper' is Bartolomei et al. as pre-registered; 'sora_v1' is ours
#: (amendment 4): SORA success at the point under the vehicle, potential shaping towards the
#: nearest SORA-safe point, a smaller descend reward, no view term, leaving the scene costs as
#: much as running out of time. Chosen by screening fixed pilots before any training.
REWARD_PRESETS = {
    'paper': {},
    'sora_v1': dict(success_rule='sora', shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0),
    # amendment 9: landable ground, soft preferred, graded hazard penalties, 2 m around people and vehicles
    'zemin_v1': dict(success_rule='zemin', shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0),
    # amendment 11: zemin_v1 with hard ground worth +5 instead of +30, and shaping that heads for soft ground
    'zemin_v2': dict(success_rule='zemin', shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0,
                     land_rewards={**ZEMIN_REWARDS, 1: 5.0}, soft_bias_m=10.0),
}


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
        n_ch = 3 if self.cfg.obs_mode == 'sem_depth_sora' else 2
        self.observation_space = gym.spaces.Box(0.0, 1.0, (n_ch, n, n), np.float32)
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
        cfg, sc = self.cfg, self.scene
        pos, R = self.veh.delayed_pose()
        elev = None
        if cfg.sem_source == 'gt' and cfg.depth_mode == 'flat' and cfg.sora_elev_tau < 0:
            sem, depth = self.cam.semantic_depth(sc, pos, R)
            seen = sem
        else:
            X, Y, depth = ground_hits(self.cam.rays, pos, R)
            ok = np.isfinite(depth)
            sem = np.full(depth.shape, N_CLASSES - 1, np.uint8)
            sem[ok] = sc.classes_at(X[ok], Y[ok])
            seen = sem
            if cfg.sem_source == 'pred':
                seen = np.full(depth.shape, N_CLASSES - 1, np.uint8)
                seen[ok] = sc.values_at(sc.pred, X[ok], Y[ok], N_CLASSES - 1)
            if cfg.depth_mode == 'elev' or cfg.sora_elev_tau >= 0:
                elev = np.zeros(depth.shape, np.float32)
                elev[ok] = sc.values_at(sc.elev, X[ok], Y[ok], 0).astype(np.float32) / 255.0
        if cfg.binary:
            ch0 = self._safe[seen].astype(np.float32)
        else:
            ch0 = seen.astype(np.float32) / (N_CLASSES - 1)
        if cfg.depth_mode == 'elev':
            ch1 = elev
        else:
            ch1 = np.clip(np.where(np.isfinite(depth), depth, cfg.depth_norm_m) / cfg.depth_norm_m, 0, 1).astype(np.float32)
        chans = [ch0, ch1]
        if cfg.obs_mode == 'sem_depth_sora':
            if cfg.success_rule == 'zemin':
                # amendment 9: the channel marks the rule's own target, landable and clear of the buffer classes
                sora = sora_channel(seen, pos[2], cfg.buffer_m, hazard_classes=cfg.buffer_classes)
            else:
                sora = sora_channel(seen, pos[2], cfg.sora_m)
            if cfg.sora_elev_tau >= 0:
                sora &= elev <= cfg.sora_elev_tau
            chans.append(sora.astype(np.float32))
        obs = np.stack(chans)
        return obs, sem, depth

    def _potential(self, pos):
        """Shaping potential: closer to SORA-safe ground is higher. Uses the true state, which the
        policy never sees -- it is a training signal only (Ng, Harada, Russell 1999: potential-based
        shaping leaves the optimal policy unchanged)."""
        if self.cfg.shaping_k == 0.0:
            return 0.0
        if self.cfg.success_rule == 'zemin':
            _, _, d = self.scene.nearest_target(pos[0], pos[1], self.cfg.buffer_classes, self.cfg.buffer_m)
            if self.cfg.soft_bias_m >= 0:
                # amendment 11: soft ground pulls unless it is more than soft_bias_m farther than any target
                _, _, d_soft = self.scene.nearest_target(pos[0], pos[1], self.cfg.buffer_classes, self.cfg.buffer_m,
                                                         self.cfg.soft_classes)
                d = min(d_soft, d + self.cfg.soft_bias_m)
        else:
            _, _, d = self.scene.nearest_sora_safe(pos[0], pos[1], self.cfg.sora_m)
        return -self.cfg.shaping_k * min(d, self.cfg.shaping_dmax)

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
        if self.cfg.mirror and rng.random() < 0.5:
            self.scene = MirroredScene(self.scene)      # amendment 9: the same ground seen in a mirror
        params = self.cfg.dynamics
        if options and 'dynamics' in options:
            params = options['dynamics']
        elif self.cfg.randomise_dynamics:
            params = params.randomised(rng)
        pos, yaw = self._start(rng, options)
        self.veh = Vehicle(params, pos, yaw)
        self.steps = 0
        self._phi = self._potential(pos)
        obs, _, _ = self._observe()
        self._last_obs = obs
        info = {'scene': self.scene.name, 'start': (*pos, yaw),
                'dynamics': params}
        return obs, info

    def step(self, action):
        cfg = self.cfg
        a = int(action)
        shielded = False
        if cfg.shield_m >= 0 and cfg.obs_mode == 'sem_depth_sora':
            # amendment 8: the shield is part of the vehicle, so the policy learns with it in the loop
            a, shielded = shield(a, self._last_obs, self.veh.delayed_pose()[0][2], cfg.shield_m)
        self.veh.step(self._v_cmd(a), cfg.step_s)
        self.steps += 1
        pos = self.veh.pos
        obs, sem, depth = self._observe()
        self._last_obs = obs

        safe_share = float(self._safe[sem].mean())
        r_s = cfg.sem_good * safe_share + cfg.sem_bad * (1.0 - safe_share)
        d_min = float(np.min(depth))
        r_c = 0.0
        if cfg.robot_r < d_min < cfg.d_star:
            r_c = -1.0 / (d_min - cfg.robot_r)
        r_a = cfg.a_descend if a == 9 else (cfg.a_halt if a == 0 else cfg.a_lateral)

        outcome, r_t_end = None, 0.0
        landed, majority_ok, point_ok, land_cls = False, False, False, -1
        if not self.scene.inside(pos[0], pos[1]):
            outcome, r_t_end = 'out_of_bounds', cfg.out_of_bounds
        elif d_min <= cfg.robot_r:
            outcome, r_t_end = 'collision', cfg.collision
        elif pos[2] <= cfg.target_h:
            landed = True
            now, _ = self.cam.semantic_depth(self.scene, pos, self.veh.attitude())
            majority = int(np.bincount(now.ravel(), minlength=N_CLASSES).argmax())
            majority_ok = bool(self._safe[majority])
            if cfg.sora_metric or cfg.success_rule == 'sora':
                point_ok = self.scene.is_sora_safe(pos[0], pos[1], cfg.sora_m)
            land_cls = self.scene.landing_class(pos[0], pos[1], cfg.buffer_classes, cfg.buffer_m)
            if cfg.success_rule == 'zemin':
                # amendment 9: the class landed on sets the reward (a buffer class counts when it is near)
                ok = bool(self._safe[land_cls])
                r_t_end = float(cfg.land_rewards[land_cls])
            else:
                ok = point_ok if cfg.success_rule == 'sora' else majority_ok
                r_t_end = cfg.land_good if ok else cfg.land_bad
            outcome = 'safe_landing' if ok else 'unsafe_landing'
        elif self.veh.t >= cfg.max_t - 1e-9:
            outcome, r_t_end = 'timeout', cfg.timeout

        done = outcome is not None
        r_t = 0.0 if done else cfg.r_step
        phi = 0.0 if done else self._potential(pos)
        r_shape = cfg.gamma * phi - self._phi
        self._phi = phi
        reward = cfg.w_t * r_t + cfg.w_s * r_s + cfg.w_c * r_c + cfg.w_a * r_a + r_shape + r_t_end
        info = {'r_s': r_s, 'r_c': r_c, 'r_a': r_a, 'r_shape': r_shape, 'r_end': r_t_end, 'action': a,
                'shielded': shielded}
        if done:
            sora = self.scene.hazard_distance(pos[0], pos[1]) if cfg.sora_metric else float('nan')
            info.update(outcome=outcome, success=outcome == 'safe_landing', t=self.veh.t,
                        landing_xy=(float(pos[0]), float(pos[1])), sora_distance_m=sora,
                        sora_ok=bool(outcome == 'safe_landing' and sora >= cfg.sora_m),
                        majority_success=landed and majority_ok, sora_success=landed and point_ok,
                        landing_class=int(land_cls), zemin_success=bool(landed and self._safe[land_cls]),
                        soft_landing=bool(landed and land_cls == 0))
        return obs, float(reward), done, False, info
