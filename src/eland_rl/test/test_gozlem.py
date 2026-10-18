"""Amendment 16: extra observation channels (risk, hedef, hafiza)."""
import math

import numpy as np
import pytest

from eland_rl import gozlem
from eland_rl.dynamics import DynamicsParams
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scene import Scene

NO_LAG = DynamicsParams(tau_xy=0.5, tau_z=0.5, a_max=3.0, latency_s=0.0, cmd_delay_xy=0.0, cmd_delay_z=0.0,
                        tilt_bias_deg=0.0)


def sahne(cls=2, size=(120.0, 120.0), res=0.1):
    w, h = int(size[0] / res), int(size[1] / res)
    return Scene(np.full((h, w), cls, np.uint8), size, name=f'duz{cls}')


def boya(sc, x0, x1, y0, y1, cls):
    """Paint world rectangle [x0, x1] x [y0, y1] (metres) with a class."""
    H, W = sc.mask.shape
    c0, c1 = int((x0 / sc.size[0] + 0.5) * W), int((x1 / sc.size[0] + 0.5) * W)
    r0, r1 = int((0.5 - y1 / sc.size[1]) * H), int((0.5 - y0 / sc.size[1]) * H)
    sc.mask[r0:r1, c0:c1] = cls
    return sc


def ortam(sc, kanallar, yaw=0.0, h=20.0):
    env = LandingEnv([sc], EnvConfig(obs_mode='sem_depth_sora', kanallar=kanallar, **REWARD_PRESETS['zemin_v3']))
    obs, _ = env.reset(seed=0, options={'start': (0.0, 0.0, h, yaw), 'dynamics': NO_LAG})
    return env, obs


def test_risk_channel_and_shape():
    env, obs = ortam(boya(sahne(0), -5, 5, -5, 5, 3), ('risk',))
    assert obs.shape == (4, 128, 128) and env.observation_space.shape == (4, 128, 128)
    assert obs[3, 64, 64] == pytest.approx(gozlem.RISK[3]) and obs[3, 2, 2] == pytest.approx(0.0)


def test_unknown_channel_is_refused():
    with pytest.raises(ValueError):
        LandingEnv([sahne()], EnvConfig(obs_mode='sem_depth_sora', kanallar=('yok',)))


def test_hedef_points_at_the_grass_beside_the_vehicle():
    # asphalt everywhere, a grass square 6..14 m to the vehicle's right (yaw 0: right = -y)
    env, obs = ortam(boya(sahne(2), -4, 4, -14, -6, 0), ('hedef',))
    blob = obs[3]
    i, j = np.unravel_index(int(np.argmax(blob)), blob.shape)
    assert obs[2, i, j] == 1.0                     # on a target pixel
    assert j > 64 and abs(i - 64) < 12             # to the right of the centre, about level with it
    env, obs = ortam(sahne(2), ('hedef',))         # no target in view: nothing to point at
    assert not obs[3].any()


def test_memory_keeps_what_left_the_view():
    sc = boya(sahne(0), 10, 15, -3, 3, 3)          # a structure 10..15 m ahead (yaw 0: ahead = +x)
    env, obs = ortam(sc, ('hafiza',))
    s = 48.0 / 128
    i = int(63.5 - 12.5 / s)                       # row of x = 12.5 m ahead
    assert obs[3, i, 64] == pytest.approx(gozlem.RISK[3])
    assert obs[3, 64, 64] == pytest.approx(0.0)    # grass under the vehicle
    while env.veh.pos[2] > 7.0:
        obs, _, done, _, _ = env.step(9)
        assert not done
    assert not (obs[0] == 3 / 7).any()              # the structure is out of the camera's view now ...
    assert obs[3, i, 64] == pytest.approx(gozlem.RISK[3])   # ... but still in the memory
    assert obs[3, 23, 10] == pytest.approx(0.0)    # grass seen from 20 m (15 m ahead, 20 m left) stays remembered
    assert obs[3, 2, 2] == pytest.approx(gozlem.BILINMEYEN)   # 23 m ahead was never in view


def test_memory_is_heading_up():
    sc = boya(sahne(0), 10, 15, -3, 3, 3)          # structure at +x; with the nose along +y it is on the right
    env, obs = ortam(sc, ('hafiza',), yaw=math.pi / 2)
    s = 48.0 / 128
    j = int(63.5 + 12.5 / s)
    assert obs[3, 64, j] == pytest.approx(gozlem.RISK[3])
    assert obs[3, 64, 127 - j] == pytest.approx(0.0)


def test_memory_resets_and_unknown_is_risky():
    sc = sahne(0, size=(40.0, 40.0))
    env, obs = ortam(sc, ('hafiza',), h=6.0)       # narrow view: most of the 48 m map never seen
    assert obs[3, 0, 0] == pytest.approx(gozlem.BILINMEYEN)
    env.reset(seed=1, options={'start': (5.0, 5.0, 6.0, 0.0), 'dynamics': NO_LAG})
    assert (env.hafiza.izgara >= 0).mean() < 0.05  # only the new view, nothing from the last episode


def test_all_three_in_order():
    env, obs = ortam(sahne(0), ('hafiza', 'risk', 'hedef'))
    assert obs.shape == (6, 128, 128)
    assert obs[3].max() <= 0.15 and obs[4].max() == pytest.approx(1.0, abs=1e-3)   # risk, then hedef
    assert obs[5, 64, 64] == pytest.approx(0.0)                                    # then hafiza
