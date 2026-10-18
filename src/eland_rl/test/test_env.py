"""Unit tests of the light environment: geometry conventions, dynamics, reward, episode ends."""
import math

import cv2
import numpy as np
import pytest

from eland_rl.camera import Camera, body_rays, ground_hits, nearest_source_index, rotation
from eland_rl.dynamics import DynamicsParams, Vehicle
from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scene import Scene

LEVEL = rotation((0, 0, 1), 0.0)
NO_LAG = DynamicsParams(tau_xy=0.5, tau_z=0.5, a_max=3.0, latency_s=0.0, cmd_delay_xy=0.0, cmd_delay_z=0.0,
                        tilt_bias_deg=0.0)
IDEAL = dict(cmd_delay_xy=0.0, cmd_delay_z=0.0, tilt_bias_deg=0.0)


def flat_scene(cls=0, size=(200.0, 150.0), res=0.1):
    w, h = int(size[0] / res), int(size[1] / res)
    return Scene(np.full((h, w), cls, np.uint8), size, name=f'flat{cls}')


def test_policy_rays_are_what_inter_nearest_keeps():
    src = np.arange(240 * 320, dtype=np.float32).reshape(240, 320)
    want = cv2.resize(src, (128, 128), interpolation=cv2.INTER_NEAREST)
    got = src[np.ix_(nearest_source_index(240, 128), nearest_source_index(320, 128))]
    assert np.array_equal(want, got)


def test_level_camera_depth_is_height():
    _, _, t = ground_hits(body_rays(64, 48), np.array([3.0, -2.0, 17.0]), LEVEL)
    assert np.allclose(t, 17.0)


@pytest.mark.parametrize('yaw,patch_xy', [(0.0, (8.0, 0.0)), (math.pi / 2, (0.0, 8.0))])
def test_image_up_is_the_nose(yaw, patch_xy):
    sc = flat_scene(0)
    H, W = sc.mask.shape
    # a structure patch 8 m ahead of the nose
    cx = int((patch_xy[0] / sc.size[0] + 0.5) * W)
    cy = int((0.5 - patch_xy[1] / sc.size[1]) * H)
    sc.mask[cy - 20:cy + 20, cx - 20:cx + 20] = 3
    sem, _ = Camera().semantic_depth(sc, np.array([0.0, 0.0, 20.0]), rotation((0, 0, 1), yaw))
    rows, cols = np.nonzero(sem == 3)
    assert rows.size > 0
    assert rows.mean() < 64 - 5            # upper half of the image
    assert abs(cols.mean() - 64) < 5       # centred left-right


def test_forward_acceleration_tilts_camera_backwards():
    R = rotation((2.0, 0.0, 9.81), 0.0)
    X, _, _ = ground_hits(np.array([[0.0, 0.0, -1.0]]), np.array([0.0, 0.0, 25.0]), R)
    # 11.5 deg nose-down at 25 m: centre ray lands ~5.1 m behind
    assert X[0] == pytest.approx(-25.0 * 2.0 / 9.81, rel=1e-6)


def test_first_order_step_response():
    v = Vehicle(DynamicsParams(tau_xy=0.5, tau_z=0.5, a_max=100.0, latency_s=0.0, substep_s=0.001, **IDEAL), (0, 0, 20), 0.0)
    v.step((1.0, 0.0, 0.0), 0.5)
    assert v.vel[0] == pytest.approx(1 - math.exp(-1), abs=0.01)


def test_acceleration_cap():
    v = Vehicle(DynamicsParams(tau_xy=0.01, tau_z=0.5, a_max=2.0, latency_s=0.0, **IDEAL), (0, 0, 20), 0.0)
    v.step((1.0, 1.0, 0.0), 0.25)
    assert np.hypot(*v.acc[:2]) <= 2.0 + 1e-9


def test_latency_shows_an_older_pose():
    v = Vehicle(DynamicsParams(tau_xy=0.1, tau_z=0.1, a_max=10.0, latency_s=0.2, **IDEAL), (0, 0, 20), 0.0)
    v.step((1.0, 0.0, 0.0), 1.0)
    pos, _ = v.delayed_pose()
    assert pos[0] < v.pos[0] - 0.15


def test_command_delay():
    v = Vehicle(DynamicsParams(tau_xy=0.1, tau_z=0.1, a_max=10.0, latency_s=0.0, cmd_delay_xy=0.25,
                               cmd_delay_z=0.1, tilt_bias_deg=0.0), (0, 0, 20), 0.0)
    v.step((1.0, 0.0, 1.0), 0.2)
    assert v.vel[0] == 0.0 and v.vel[2] > 0.0     # z has started, xy has not
    v.step((1.0, 0.0, 1.0), 0.25)
    assert v.vel[0] > 0.3


def test_trim_tilt_at_hover():
    v = Vehicle(DynamicsParams(tilt_bias_deg=1.0, tilt_bias_dir=0.0), (0, 0, 20), 0.0)
    R = v.attitude()
    assert math.degrees(math.acos(R[2, 2])) == pytest.approx(1.0, abs=1e-6)


def test_measured_defaults():
    p = DynamicsParams()
    assert (p.tau_xy, p.a_max, p.cmd_delay_xy, p.tau_z, p.cmd_delay_z) == (0.50, 2.0, 0.24, 0.15, 0.10)


def _run(env, action, start):
    obs, _ = env.reset(seed=0, options={'start': start, 'dynamics': NO_LAG})
    total = 0.0
    for _ in range(1000):
        obs, r, term, trunc, info = env.step(action)
        total += r
        if term or trunc:
            return total, info
    raise AssertionError('episode did not end')


def test_descend_on_grass_is_a_safe_landing():
    env = LandingEnv([flat_scene(0)])
    total, info = _run(env, 9, (0.0, 0.0, 20.0, 0.0))
    assert info['outcome'] == 'safe_landing' and info['success']
    assert info['sora_ok'] and math.isinf(info['sora_distance_m'])
    assert 7.0 < info['t'] < 9.0           # 15 m at 2 m/s plus the lag
    assert total > 50


def test_descend_on_a_roof_is_unsafe():
    env = LandingEnv([flat_scene(3)])
    total, info = _run(env, 9, (0.0, 0.0, 20.0, 0.0))
    assert info['outcome'] == 'unsafe_landing' and not info['success']
    assert total < 0


def test_safe_hard_counts_as_safe():
    env = LandingEnv([flat_scene(1)])
    _, info = _run(env, 9, (0.0, 0.0, 20.0, 0.0))
    assert info['success']


def test_leaving_the_scene_ends_the_episode():
    env = LandingEnv([flat_scene(0, size=(20.0, 20.0))])
    _, info = _run(env, 1, (0.0, 0.0, 25.0, 0.0))
    assert info['outcome'] == 'out_of_bounds'


def test_halting_times_out():
    env = LandingEnv([flat_scene(0)], EnvConfig(max_t=5.0))
    total, info = _run(env, 0, (0.0, 0.0, 25.0, 0.0))
    assert info['outcome'] == 'timeout'
    assert total == pytest.approx(19 * (-0.2 + 1.0 - 0.5) + (1.0 - 0.5) - 50.0)


def test_binary_channel():
    env = LandingEnv([flat_scene(1)], EnvConfig(binary=True))
    obs, _ = env.reset(seed=1, options={'start': (0.0, 0.0, 20.0, 0.3)})
    assert np.all(obs[0] == 1.0)
    obs, _ = env.reset(seed=1, options={'start': (95.0, 0.0, 20.0, 0.3)})   # half the view off the photo
    assert 0.2 < obs[0].mean() < 0.8


def test_random_start_respects_min_inside():
    sc = flat_scene(0, size=(120.0, 80.0))
    env = LandingEnv([sc])
    for s in range(20):
        _, info = env.reset(seed=s)
        x, y, h, yaw = info['start']
        f = env.cam.inside_fraction(sc, np.array([x, y, h]), rotation((0, 0, 1), yaw))
        assert f >= 0.7 and 20.0 <= h <= 30.0


def test_gymnasium_api():
    from gymnasium.utils.env_checker import check_env
    check_env(LandingEnv([flat_scene(0)]), skip_render_check=True)


def _grass_with_person():
    sc = flat_scene(0, size=(60.0, 40.0))
    H, W = sc.mask.shape
    sc.mask[H // 2 - 3:H // 2 + 3, W // 2 - 3:W // 2 + 3] = 6     # a person at the origin
    return sc


def test_sora_distance_and_nearest_point():
    sc = _grass_with_person()
    assert not sc.is_sora_safe(0.0, 0.0)
    assert not sc.is_sora_safe(2.0, 0.0)                 # grass, but 2 m from the person
    assert sc.is_sora_safe(4.0, 0.0)
    tx, ty, d = sc.nearest_sora_safe(0.0, 0.0)
    assert 3.0 <= math.hypot(tx, ty) <= 3.5 and 3.0 <= d <= 3.5


def test_sora_success_rule_and_info():
    sc = _grass_with_person()
    # majority rule: the 5 m view is almost all grass -> success; SORA rule: on the person -> failure
    for rule, ok in (('majority', True), ('sora', False)):
        env = LandingEnv([sc], EnvConfig(success_rule=rule))
        _, info = _run(env, 9, (0.0, 0.0, 20.0, 0.0))
        assert info['success'] is ok
        assert info['majority_success'] and not info['sora_success']


def test_shaping_pays_for_moving_towards_safe_ground():
    sc = _grass_with_person()
    env = LandingEnv([sc], EnvConfig(shaping_k=1.0, gamma=1.0))
    env.reset(seed=0, options={'start': (0.0, 0.0, 25.0, 0.0), 'dynamics': NO_LAG})
    gains = [env.step(1)[4]['r_shape'] for _ in range(12)]       # 1 = nose = +x, away from the person
    assert sum(gains) > 2.0
    env.reset(seed=0, options={'start': (0.0, 0.0, 25.0, 0.0), 'dynamics': NO_LAG})
    assert sum(env.step(9)[4]['r_shape'] for _ in range(4)) == pytest.approx(0.0, abs=1e-9)


def test_sora_channel_keeps_three_metres_from_a_person():
    from eland_rl.camera import sora_channel
    sem = np.zeros((128, 128), np.uint8)
    sem[63:65, 63:65] = 6                                  # a person in the middle
    h = 10.0                                               # 128 px across 2*10*tan(49.85 deg) = 23.7 m
    ch = sora_channel(sem, h)
    px = 2 * h * math.tan(1.74 / 2) / 128                  # ~0.185 m per column
    assert not ch[64, 64]
    assert not ch[64, 64 + int(2.5 / px)]                  # 2.5 m to the side: too close
    assert ch[64, 64 + int(3.6 / px)]                      # 3.6 m: clear
    assert ch[5, 5] and ch.mean() > 0.8


def test_three_channel_observation():
    from gymnasium.utils.env_checker import check_env
    env = LandingEnv([_grass_with_person()], EnvConfig(obs_mode='sem_depth_sora', success_rule='sora'))
    obs, _ = env.reset(seed=0, options={'start': (0.0, 0.0, 10.0, 0.0), 'dynamics': NO_LAG})
    assert obs.shape == (3, 128, 128)
    assert obs[2, 64, 64] == 0.0 and obs[2, 5, 5] == 1.0
    check_env(LandingEnv([flat_scene(0)], EnvConfig(obs_mode='sem_depth_sora')), skip_render_check=True)


def test_predicted_semantics_and_elevation_channels():
    sc = flat_scene(0, size=(60.0, 40.0))
    sc.pred = np.full_like(sc.mask, 3)                     # v3 'sees' a roof everywhere
    sc.elev = np.zeros_like(sc.mask)
    H, W = sc.mask.shape
    sc.elev[:, : W // 2] = 255                             # west half raised
    start = {'start': (0.0, 0.0, 10.0, 0.0), 'dynamics': NO_LAG}
    obs, _ = LandingEnv([sc], EnvConfig(obs_mode='sem_depth_sora', sem_source='pred')).reset(seed=0, options=start)
    assert np.allclose(obs[0], 3 / 7) and obs[2].sum() == 0  # classes and SORA channel follow the prediction
    env = LandingEnv([sc], EnvConfig(obs_mode='sem_depth_sora', depth_mode='elev', sora_elev_tau=0.5))
    obs, _ = env.reset(seed=0, options=start)
    assert 0.3 < obs[1].mean() < 0.7                       # elevation channel: half the view raised
    assert obs[2].sum() > 0 and obs[2][obs[1] > 0.5].sum() == 0   # raised pixels are never SORA-safe
    _, _, _, _, info = env.step(9)
    assert 'r_shape' in info                               # reward still from the GT world


def test_shield_inside_the_environment():
    sc = _grass_with_person()
    cfg = dict(obs_mode='sem_depth_sora', success_rule='sora')
    start = {'start': (0.0, 0.0, 8.0, 0.0), 'dynamics': NO_LAG}
    env = LandingEnv([sc], EnvConfig(**cfg))
    env.reset(seed=0, options=start)
    assert not env.step(9)[4]['shielded']                      # off by default
    env = LandingEnv([sc], EnvConfig(shield_m=10.0, **cfg))
    env.reset(seed=0, options=start)
    info = env.step(9)[4]                                      # descend onto the person at 8 m
    assert info['shielded'] and info['action'] != 9


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


# ------------------------------------------------- amendment 11: 'zemin_v2', hard ground worth less, soft pull
def _hard_with_grass(x0, x1):
    """Hard ground with a grass strip from x0 to x1 metres (full height of the scene)."""
    sc = flat_scene(1, size=(60.0, 40.0))
    H, W = sc.mask.shape
    sc.mask[:, int((x0 / 60.0 + 0.5) * W):int((x1 / 60.0 + 0.5) * W)] = 0
    return sc


@pytest.mark.parametrize('cls,reward', [(0, 50.0), (1, 5.0), (2, -40.0), (6, -100.0)])
def test_zemin_v2_terminal_reward(cls, reward):
    from eland_rl.env import REWARD_PRESETS
    env = LandingEnv([flat_scene(cls)], EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['zemin_v2']))
    _, info = _run(env, 9, (0.0, 0.0, 20.0, 0.0))
    assert info['r_end'] == reward and info['zemin_success'] is (cls in (0, 1))


def test_soft_target_grid_and_mirror():
    from eland_rl.scene import MirroredScene
    sc = _hard_with_grass(5.0, 15.0)
    assert sc.nearest_target(0.0, 0.0, (6, 5), 2.0)[2] == 0.0                 # hard ground is a target
    tx, _, d = sc.nearest_target(0.0, 0.0, (6, 5), 2.0, (0,))
    assert 4.9 <= d <= 5.2 and 4.9 <= tx <= 5.2                               # the strip's near edge
    mx, _, md = MirroredScene(sc).nearest_target(0.0, 0.0, (6, 5), 2.0, (0,))
    assert (mx, md) == (-tx, d)
    assert sc.nearest_target(0.0, 0.0, (6, 5), 2.0)[2] == 0.0                 # cached grids stay apart


def _shaping_gain(env, action, n):
    env.reset(seed=0, options={'start': (0.0, 0.0, 25.0, 0.0), 'dynamics': NO_LAG})
    return sum(env.step(action)[4]['r_shape'] for _ in range(n))


def test_soft_bias_pulls_towards_near_grass_only():
    from eland_rl.env import REWARD_PRESETS
    v1 = {**REWARD_PRESETS['zemin_v1'], 'gamma': 1.0}
    v2 = {**REWARD_PRESETS['zemin_v2'], 'gamma': 1.0}
    near = _hard_with_grass(5.0, 15.0)
    # zemin_v1: standing on hard ground is already on target, moving pays nothing
    assert _shaping_gain(LandingEnv([near], EnvConfig(**v1)), 1, 12) == pytest.approx(0.0, abs=1e-9)
    # zemin_v2: grass 5 m away (< 10 m bias) pulls; moving towards it (1 = nose = +x) pays, away costs
    assert _shaping_gain(LandingEnv([near], EnvConfig(**v2)), 1, 12) > 2.0
    assert _shaping_gain(LandingEnv([near], EnvConfig(**v2)), 5, 12) < -2.0
    # grass 15 m away: further than hard ground + 10 m, so no pull
    far = _hard_with_grass(15.0, 25.0)
    assert _shaping_gain(LandingEnv([far], EnvConfig(**v2)), 1, 12) == pytest.approx(0.0, abs=1e-9)


# ------------------------------------------------- amendment 12: training under the test's time limit
def test_training_time_limit_switch():
    import argparse
    from eland_rl.train import zemin_extra
    a = argparse.Namespace(mirror=False, reward='zemin_v1', land_hard=None, max_t=None)
    assert 'max_t' not in zemin_extra(a)                       # earlier runs: EnvConfig's 90 s
    a.max_t = 30.0
    assert zemin_extra(a)['max_t'] == 30.0
    env = LandingEnv([flat_scene(0)], EnvConfig(**zemin_extra(a)))
    _, info = _run(env, 0, (0.0, 0.0, 25.0, 0.0))               # hold: times out at the limit
    assert info['outcome'] == 'timeout' and abs(info['t'] - 30.0) < 0.3


# ------------------------------------------------- amendment 13: sliding descents
def test_sliding_descent_actions():
    from eland_rl.env import descends, lateral_index
    assert LandingEnv([flat_scene(0)]).action_space.n == 10                   # earlier runs unchanged
    env = LandingEnv([flat_scene(0)], EnvConfig(diag_actions=True))
    assert env.action_space.n == 18
    assert [lateral_index(a) for a in (1, 8, 10, 17)] == [0, 7, 0, 7]
    assert descends(9) and descends(13) and not descends(0) and not descends(4)
    env.reset(seed=0, options={'start': (0.0, 0.0, 25.0, 0.0), 'dynamics': NO_LAG})
    p0 = env.veh.pos.copy()
    for _ in range(8):
        info = env.step(10)[4]                                                 # nose (+x) while descending
    d = env.veh.pos - p0
    assert d[0] > 1.0 and abs(d[1]) < 0.1 and d[2] < -2.5                     # moved forward and down together
    assert info['r_a'] == pytest.approx(0.5 * 0 + EnvConfig().a_descend + EnvConfig().a_lateral)


def test_shield_treats_a_sliding_descent_as_a_descent():
    from eland_rl.pilots import shield
    obs = np.zeros((3, 128, 128), np.float32)
    obs[2, :, 100:] = 1.0                                                      # safe only on the right
    for a in (9, 13):
        b, over = shield(a, obs, 8.0, 10.0)
        assert over and 1 <= b <= 8                                             # a plain slide instead
    assert shield(13, obs, 12.0, 10.0) == (13, False)                           # above 10 m: untouched
    assert shield(4, obs, 8.0, 10.0) == (4, False)                              # slides pass


# ------------------------------------------------- amendment 14: 'zemin_v3', rushing onto asphalt costs more than a time-out
@pytest.mark.parametrize('cls,reward', [(0, 50.0), (1, 30.0), (2, -60.0), (3, -60.0), (6, -100.0)])
def test_zemin_v3_terminal_reward(cls, reward):
    from eland_rl.env import REWARD_PRESETS
    cfg = EnvConfig(obs_mode='sem_depth_sora', **REWARD_PRESETS['zemin_v3'])
    assert cfg.a_descend == 1.0 and cfg.land_rewards[7] == -60.0 and cfg.land_rewards[2] < cfg.timeout
    _, info = _run(LandingEnv([flat_scene(cls)], cfg), 9, (0.0, 0.0, 20.0, 0.0))
    assert info['r_end'] == reward and info['zemin_success'] is (cls in (0, 1))
