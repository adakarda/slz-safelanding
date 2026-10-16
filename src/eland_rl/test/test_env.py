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
