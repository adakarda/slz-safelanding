"""Duzeltme 9: 'zemin' inis kurali (sinifa gore terminal odul, insan/arac icin 2 m tampon), aynalama,
duz alcalma + kalkan taban cizgisi. Eski ayarlarin sonucu degismez.

    python yama_zemin.py <eland_rl paket klasoru> <test_env.py>
"""
import os
import sys

d, test_path = sys.argv[1], sys.argv[2]


def patch(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, (path, old[:70])
        s = s.replace(old, new)
    open(path, 'w', encoding='utf-8', newline='\n').write(s)


def P(n):
    return os.path.join(d, n)


# ------------------------------------------------------------------ env.py
patch(P('env.py'), [
    ("from .dynamics import DynamicsParams, Vehicle\n",
     "from .dynamics import DynamicsParams, Vehicle\nfrom .scene import MirroredScene\n"),
    ("N_CLASSES = 8                       # seven taxonomy classes + UNKNOWN\n",
     "N_CLASSES = 8                       # seven taxonomy classes + UNKNOWN\n\n"
     "#: Amendment 9: terminal reward by the class landed on (taxonomy index; 7 = unknown / off the photo).\n"
     "#: Soft ground over hard ground; hazards ordered as SORA ranks the harm, the worst below a time-out.\n"
     "ZEMIN_REWARDS = {0: 50.0, 1: 30.0, 2: -40.0, 3: -60.0, 4: -70.0, 5: -90.0, 6: -100.0, 7: -50.0}\n"),
    ("    randomise_dynamics: bool = True\n",
     "    randomise_dynamics: bool = True\n"
     "    # Amendment 9 ('zemin' rule): success is a landable class at the point under the vehicle with no\n"
     "    # buffer class closer than buffer_m; the terminal reward is set by the class landed on.\n"
     "    land_rewards: dict = field(default_factory=lambda: dict(ZEMIN_REWARDS))\n"
     "    buffer_classes: tuple = (6, 5)  # person, vehicle-animal; most severe first\n"
     "    buffer_m: float = 2.0\n"
     "    sora_metric: bool = True        # also judge landings by the 3 m SORA rule (a metric; one grid per scene)\n"
     "    mirror: bool = False            # each episode sees its scene mirrored with p = 0.5\n"),
    ("    'sora_v1': dict(success_rule='sora', shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0),\n",
     "    'sora_v1': dict(success_rule='sora', shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0),\n"
     "    # amendment 9: landable ground, soft preferred, graded hazard penalties, 2 m around people and vehicles\n"
     "    'zemin_v1': dict(success_rule='zemin', shaping_k=2.0, a_descend=0.5, w_s=0.0, out_of_bounds=-50.0),\n"),
    ("        if cfg.obs_mode == 'sem_depth_sora':\n"
     "            sora = sora_channel(seen, pos[2], cfg.sora_m)\n",
     "        if cfg.obs_mode == 'sem_depth_sora':\n"
     "            if cfg.success_rule == 'zemin':\n"
     "                # amendment 9: the channel marks the rule's own target, landable and clear of the buffer classes\n"
     "                sora = sora_channel(seen, pos[2], cfg.buffer_m, hazard_classes=cfg.buffer_classes)\n"
     "            else:\n"
     "                sora = sora_channel(seen, pos[2], cfg.sora_m)\n"),
    ("        _, _, d = self.scene.nearest_sora_safe(pos[0], pos[1], self.cfg.sora_m)\n",
     "        if self.cfg.success_rule == 'zemin':\n"
     "            _, _, d = self.scene.nearest_target(pos[0], pos[1], self.cfg.buffer_classes, self.cfg.buffer_m)\n"
     "        else:\n"
     "            _, _, d = self.scene.nearest_sora_safe(pos[0], pos[1], self.cfg.sora_m)\n"),
    ("            self.scene = self.scenes[rng.integers(len(self.scenes))]\n"
     "        params = self.cfg.dynamics\n",
     "            self.scene = self.scenes[rng.integers(len(self.scenes))]\n"
     "        if self.cfg.mirror and rng.random() < 0.5:\n"
     "            self.scene = MirroredScene(self.scene)      # amendment 9: the same ground seen in a mirror\n"
     "        params = self.cfg.dynamics\n"),
    ("        landed, majority_ok, point_ok = False, False, False\n",
     "        landed, majority_ok, point_ok, land_cls = False, False, False, -1\n"),
    ("            point_ok = self.scene.is_sora_safe(pos[0], pos[1], cfg.sora_m)\n"
     "            ok = point_ok if cfg.success_rule == 'sora' else majority_ok\n"
     "            outcome = 'safe_landing' if ok else 'unsafe_landing'\n"
     "            r_t_end = cfg.land_good if ok else cfg.land_bad\n",
     "            if cfg.sora_metric or cfg.success_rule == 'sora':\n"
     "                point_ok = self.scene.is_sora_safe(pos[0], pos[1], cfg.sora_m)\n"
     "            land_cls = self.scene.landing_class(pos[0], pos[1], cfg.buffer_classes, cfg.buffer_m)\n"
     "            if cfg.success_rule == 'zemin':\n"
     "                # amendment 9: the class landed on sets the reward (a buffer class counts when it is near)\n"
     "                ok = bool(self._safe[land_cls])\n"
     "                r_t_end = float(cfg.land_rewards[land_cls])\n"
     "            else:\n"
     "                ok = point_ok if cfg.success_rule == 'sora' else majority_ok\n"
     "                r_t_end = cfg.land_good if ok else cfg.land_bad\n"
     "            outcome = 'safe_landing' if ok else 'unsafe_landing'\n"),
    ("        info = {'r_s': r_s, 'r_c': r_c, 'r_a': r_a, 'r_shape': r_shape, 'action': a, 'shielded': shielded}\n",
     "        info = {'r_s': r_s, 'r_c': r_c, 'r_a': r_a, 'r_shape': r_shape, 'r_end': r_t_end, 'action': a,\n"
     "                'shielded': shielded}\n"),
    ("            sora = self.scene.hazard_distance(pos[0], pos[1])\n",
     "            sora = self.scene.hazard_distance(pos[0], pos[1]) if cfg.sora_metric else float('nan')\n"),
    ("                        majority_success=landed and majority_ok, sora_success=landed and point_ok)\n",
     "                        majority_success=landed and majority_ok, sora_success=landed and point_ok,\n"
     "                        landing_class=int(land_cls), zemin_success=bool(landed and self._safe[land_cls]),\n"
     "                        soft_landing=bool(landed and land_cls == 0))\n"),
])

# ------------------------------------------------------------------ scene.py
NEAREST = '''def _nearest(safe, cell_m):
    """For every cell of a boolean grid: the nearest True cell (row, col) and its distance in metres."""
    gh, gw = safe.shape
    if not safe.any():
        return np.full((gh, gw), np.inf, np.float32), np.zeros((gh, gw, 2), np.int32)
    src = (~safe).astype(np.uint8)
    dist, lab = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(src == 0)
    lut = np.zeros((lab.max() + 1, 2), np.int32)
    lut[lab[ys, xs]] = np.stack([ys, xs], 1)
    return dist * np.float32(cell_m), lut[lab].astype(np.int16 if max(gh, gw) < 32767 else np.int32)


def lookup_table(mapping):'''

ZEMIN_METHODS = '''    # ------------------------------------------------- amendment 9: the 'zemin' landing rule
    def _target_grid(self, buffer_classes, buffer_m):
        """Target cells of the 'zemin' rule (landable class throughout AND >= buffer_m from the buffer
        classes), the nearest target cell and its distance for every cell, on the dist_cell_m grid."""
        key = ('zemin', tuple(sorted(buffer_classes)), round(float(buffer_m), 3))
        cache = getattr(self, '_sora_cache', {})
        if key not in cache:
            gw = max(1, int(round(self.size[0] / self.dist_cell)))
            gh = max(1, int(round(self.size[1] / self.dist_cell)))
            landable = np.isin(self.mask, list(classes.DEFAULT_SAFE_CLASSES)).astype(np.float32)
            safe = cv2.resize(landable, (gw, gh), interpolation=cv2.INTER_AREA) > 0.999
            if buffer_m > 0 and len(buffer_classes):
                hz = cv2.resize(np.isin(self.mask, list(buffer_classes)).astype(np.float32), (gw, gh),
                                interpolation=cv2.INTER_AREA) > 0
                if hz.any():
                    d = cv2.distanceTransform((~hz).astype(np.uint8), cv2.DIST_L2, 5) * np.float32(self.size[0] / gw)
                    safe &= d >= buffer_m
            cache[key] = (safe,) + _nearest(safe, self.size[0] / gw)
            self._sora_cache = cache
        return cache[key]

    def is_target(self, x, y, buffer_classes, buffer_m):
        if not self.inside(x, y):
            return False
        safe, _, _ = self._target_grid(buffer_classes, buffer_m)
        return bool(safe[self._cell(x, y, safe.shape)])

    def nearest_target(self, x, y, buffer_classes, buffer_m):
        """(tx, ty, distance_m) of the nearest 'zemin' target point; distance inf if there is none."""
        safe, dist, near = self._target_grid(buffer_classes, buffer_m)
        v, u = self._cell(x, y, safe.shape)
        gh, gw = safe.shape
        tv, tu = near[v, u]
        return ((tu + 0.5) / gw - 0.5) * self.size[0], (0.5 - (tv + 0.5) / gh) * self.size[1], float(dist[v, u])

    def near_class(self, x, y, cls, radius_m):
        """True if a pixel of class cls lies within radius_m of (x, y), at mask resolution."""
        H, W = self.mask.shape
        cu, cv = (x / self.size[0] + 0.5) * W, (0.5 - y / self.size[1]) * H
        ru, rv = radius_m / self.size[0] * W, radius_m / self.size[1] * H
        u0, u1 = max(int(cu - ru), 0), min(int(cu + ru) + 1, W)
        v0, v1 = max(int(cv - rv), 0), min(int(cv + rv) + 1, H)
        if u0 >= u1 or v0 >= v1:
            return False
        vv, uu = np.mgrid[v0:v1, u0:u1]
        d2 = ((uu + 0.5 - cu) * (self.size[0] / W)) ** 2 + ((vv + 0.5 - cv) * (self.size[1] / H)) ** 2
        return bool(((self.mask[v0:v1, u0:u1] == cls) & (d2 < radius_m * radius_m)).any())

    def landing_class(self, x, y, buffer_classes=(), buffer_m=0.0):
        """The class a landing at (x, y) is judged by under the 'zemin' rule: the most severe buffer class
        closer than buffer_m (buffer_classes ordered most severe first), else the class under the point.
        UNKNOWN off the photo."""
        if not self.inside(x, y):
            return int(classes.UNKNOWN)
        for c in buffer_classes:
            if buffer_m > 0 and self.near_class(x, y, c, buffer_m):
                return int(c)
        return int(self.classes_at(np.array([x]), np.array([y]))[0])

    @classmethod
    def from_sora7(cls, mask_path, size_m, name=None, dist_cell_m=0.1):'''

MIRROR = '''

class MirroredScene:
    """A scene seen in a mirror (x -> -x), amendment 9: a new, physically plausible nadir view that
    shares the base scene's arrays. It mirrors what the environment asks of a scene."""

    def __init__(self, base):
        self.base = base
        self.name = base.name + '|ayna'
        self.size = base.size
        self.photo = None
        self.mask, self.pred, self.elev = base.mask, base.pred, base.elev

    @property
    def half(self):
        return self.base.half

    def inside(self, x, y):
        return self.base.inside(-x, y)

    def values_at(self, arr, x, y, fill):
        return self.base.values_at(arr, -x, y, fill)

    def classes_at(self, x, y):
        return self.base.classes_at(-x, y)

    def hazard_distance(self, x, y):
        return self.base.hazard_distance(-x, y)

    def is_sora_safe(self, x, y, sora_m=3.0):
        return self.base.is_sora_safe(-x, y, sora_m)

    def nearest_sora_safe(self, x, y, sora_m=3.0):
        tx, ty, dist = self.base.nearest_sora_safe(-x, y, sora_m)
        return -tx, ty, dist

    def is_target(self, x, y, buffer_classes, buffer_m):
        return self.base.is_target(-x, y, buffer_classes, buffer_m)

    def nearest_target(self, x, y, buffer_classes, buffer_m):
        tx, ty, dist = self.base.nearest_target(-x, y, buffer_classes, buffer_m)
        return -tx, ty, dist

    def landing_class(self, x, y, buffer_classes=(), buffer_m=0.0):
        return self.base.landing_class(-x, y, buffer_classes, buffer_m)
'''

patch(P('scene.py'), [
    ("def lookup_table(mapping):", NEAREST),
    ("    @classmethod\n    def from_sora7(cls, mask_path, size_m, name=None, dist_cell_m=0.1):", ZEMIN_METHODS),
])
with open(P('scene.py'), 'a', encoding='utf-8', newline='\n') as f:
    f.write(MIRROR)

# ------------------------------------------------------------------ pilots.py
patch(P('pilots.py'), [
    ("    x, y = env.veh.pos[0], env.veh.pos[1]\n"
     "    if env.scene.is_sora_safe(x, y, env.cfg.sora_m):\n"
     "        return 9\n"
     "    pos, R = env.veh.delayed_pose()\n"
     "    X, Y, t = ground_hits(env.cam.rays, pos, R)\n"
     "    safe, _, _ = env.scene._sora_grid(env.cfg.sora_m)\n",
     "    x, y = env.veh.pos[0], env.veh.pos[1]\n"
     "    cfg = env.cfg\n"
     "    if cfg.success_rule == 'zemin':        # amendment 9: the oracle aims at the rule's own target\n"
     "        here = env.scene.is_target(x, y, cfg.buffer_classes, cfg.buffer_m)\n"
     "    else:\n"
     "        here = env.scene.is_sora_safe(x, y, cfg.sora_m)\n"
     "    if here:\n"
     "        return 9\n"
     "    pos, R = env.veh.delayed_pose()\n"
     "    X, Y, t = ground_hits(env.cam.rays, pos, R)\n"
     "    if cfg.success_rule == 'zemin':\n"
     "        safe, _, _ = env.scene._target_grid(cfg.buffer_classes, cfg.buffer_m)\n"
     "    else:\n"
     "        safe, _, _ = env.scene._sora_grid(cfg.sora_m)\n"),
])

# ------------------------------------------------------------------ train.py
ZEMIN_EXTRA = '''def zemin_extra(a):
    """Amendment 9 switches; empty for the earlier runs, so their configuration is unchanged."""
    extra = {}
    if a.mirror:
        extra['mirror'] = True
    if a.reward == 'zemin_v1':
        extra['sora_metric'] = False        # training needs no 3 m grid; evaluation keeps the metric
        if a.land_hard is not None:
            extra['land_rewards'] = {**ZEMIN_REWARDS, 1: a.land_hard}
    return extra


def main():
'''
patch(P('train.py'), [
    ("from .env import REWARD_PRESETS, EnvConfig, LandingEnv\n",
     "from .env import REWARD_PRESETS, ZEMIN_REWARDS, EnvConfig, LandingEnv\n"),
    ("                      info_keywords=('success', 'outcome', 'sora_success', 'majority_success'))\n",
     "                      info_keywords=('success', 'outcome', 'sora_success', 'majority_success', 'zemin_success',\n"
     "                                     'soft_landing', 'landing_class'))\n"),
    ("def main():\n", ZEMIN_EXTRA),
    ("    ap.add_argument('--resume', default='', help='checkpoint zip to continue from (e.g. after the host slept)')\n",
     "    ap.add_argument('--resume', default='', help='checkpoint zip to continue from (e.g. after the host slept)')\n"
     "    ap.add_argument('--mirror', action='store_true', help='amendment 9: mirror the scene in half the episodes')\n"
     "    ap.add_argument('--land-hard', type=float, default=None, help='zemin_v1: reward for landing on hard ground')\n"),
    ("                                        sora_elev_tau=a.sora_elev_tau, shield_m=a.shield_train_m), mon)\n",
     "                                        sora_elev_tau=a.sora_elev_tau, shield_m=a.shield_train_m,\n"
     "                                        **zemin_extra(a)), mon)\n"),
])

# ------------------------------------------------------------------ evaluate.py
s = open(P('evaluate.py'), encoding='utf-8').read()
imp = [ln for ln in s.splitlines() if ln.startswith('from .env import')]
assert len(imp) == 1 and 'REWARD_PRESETS' in imp[0], imp
s = s.replace(imp[0], imp[0].replace('REWARD_PRESETS', 'REWARD_PRESETS, ZEMIN_REWARDS', 1), 1)
open(P('evaluate.py'), 'w', encoding='utf-8', newline='\n').write(s)
patch(P('evaluate.py'), [
    ("    ap.add_argument('--out', required=True)\n",
     "    ap.add_argument('--land-hard', type=float, default=None, help='zemin_v1: reward for landing on hard ground')\n"
     "    ap.add_argument('--out', required=True)\n"),
    ("                                       shield_m=a.shield_train_m,\n"
     "                                       **REWARD_PRESETS[a.reward]))\n",
     "                                       shield_m=a.shield_train_m,\n"
     "                                       **({'land_rewards': {**ZEMIN_REWARDS, 1: a.land_hard}} if a.land_hard is not None else {}),\n"
     "                                       **REWARD_PRESETS[a.reward]))\n"),
    ("        from .pilots import channel_pilot\n"
     "        methods['kanal'] = channel_pilot\n",
     "        from .pilots import channel_pilot, shield as _shield\n"
     "        methods['kanal'] = channel_pilot\n"
     "        # amendment 9: straight descent behind the same shield, the rule baseline RL + shield must beat\n"
     "        methods['duz_kalkan'] = lambda o: _shield(9, o, env.veh.delayed_pose()[0][2], a.shield_m)[0]\n"),
    ("                                 sora_m=round(min(info['sora_distance_m'], 999.0), 2)))\n",
     "                                 sora_m=round(min(info['sora_distance_m'], 999.0), 2),\n"
     "                                 landing_class=info['landing_class'], zemin_success=int(info['zemin_success']),\n"
     "                                 soft=int(info['soft_landing'])))\n"),
    ("        print(f'    eylemler: dur {h[0] / tot:.2f}, yanal {sum(h[i] for i in range(1, 9)) / tot:.2f}, alcal {h[9] / tot:.2f}')\n",
     "        print(f'    eylemler: dur {h[0] / tot:.2f}, yanal {sum(h[i] for i in range(1, 9)) / tot:.2f}, alcal {h[9] / tot:.2f}')\n"
     "        lc = collections.Counter(x['landing_class'] for x in r if x['landing_class'] >= 0)\n"
     "        print(f'    zemin basari {100 * np.mean([x[\"zemin_success\"] for x in r]):5.1f} %  '\n"
     "              f'yumusak {100 * np.mean([x[\"soft\"] for x in r]):5.1f} %  inis sinifi {dict(sorted(lc.items()))}')\n"),
])

# ------------------------------------------------------------------ tests
TESTS = '''

# ------------------------------------------------- amendment 9: 'zemin' rule, buffer, mirror
def _zemin_env(sc, **kw):
    from eland_rl.env import REWARD_PRESETS
    return LandingEnv([sc], EnvConfig(obs_mode='sem_depth_sora', **{**REWARD_PRESETS['zemin_v1'], **kw}))


@pytest.mark.parametrize('cls,reward', [(0, 50.0), (1, 30.0), (2, -40.0), (3, -60.0), (4, -70.0)])
def test_zemin_terminal_reward_by_class(cls, reward):
    _, info = _run(_zemin_env(flat_scene(cls)), 9, (0.0, 0.0, 20.0, 0.0))
    assert info['landing_class'] == cls and info['r_end'] == reward
    assert info['success'] is (cls in (0, 1)) and info['zemin_success'] is (cls in (0, 1))
    assert info['soft_landing'] is (cls == 0)


def test_zemin_buffer_only_around_people_and_vehicles():
    sc = _grass_with_person()
    assert sc.landing_class(0.0, 0.0, (6, 5), 2.0) == 6        # on the person
    assert sc.landing_class(1.5, 0.0, (6, 5), 2.0) == 6        # grass inside the 2 m buffer
    assert sc.landing_class(2.8, 0.0, (6, 5), 2.0) == 0        # grass outside it; SORA's 3 m refuses it
    assert not sc.is_sora_safe(2.8, 0.0) and sc.is_target(2.8, 0.0, (6, 5), 2.0)
    roof = flat_scene(0, size=(60.0, 40.0))
    H, W = roof.mask.shape
    roof.mask[H // 2 - 3:H // 2 + 3, W // 2 - 3:W // 2 + 3] = 3  # a small structure: no buffer around it
    assert roof.landing_class(1.0, 0.0, (6, 5), 2.0) == 0


def test_zemin_channel_uses_the_smaller_buffer():
    from eland_rl.env import REWARD_PRESETS
    start = {'start': (0.0, 0.0, 10.0, 0.0), 'dynamics': NO_LAG}
    obs_z, _ = _zemin_env(_grass_with_person()).reset(seed=0, options=start)
    env_s = LandingEnv([_grass_with_person()], EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['sora_v1']))
    obs_s, _ = env_s.reset(seed=0, options=start)
    assert 0 < (obs_z[2] < 0.5).sum() < (obs_s[2] < 0.5).sum()


def test_mirrored_scene_is_the_mirror_image():
    from eland_rl.scene import MirroredScene
    sc = _grass_with_person()
    H, W = sc.mask.shape
    sc.mask[:, :W // 4] = 3                                      # a building strip on the west side
    m = MirroredScene(sc)
    xs, ys = np.array([-25.0, -10.0, 0.0, 10.0, 25.0]), np.array([5.0, -3.0, 0.0, 2.0, -7.0])
    assert np.array_equal(m.classes_at(xs, ys), sc.classes_at(-xs, ys))
    assert m.classes_at(np.array([25.0]), np.array([0.0]))[0] == 3   # the strip is now in the east
    tx, ty, dist = m.nearest_sora_safe(0.0, 0.0)
    bx, by, bdist = sc.nearest_sora_safe(0.0, 0.0)
    assert (tx, ty, dist) == (-bx, by, bdist)
    env = LandingEnv([sc], EnvConfig(mirror=True))
    assert {env.reset(seed=s)[1]['scene'] for s in range(20)} == {sc.name, sc.name + '|ayna'}
'''
with open(test_path, 'a', encoding='utf-8', newline='\n') as f:
    f.write(TESTS)
print('yama zemin tamam:', d)
