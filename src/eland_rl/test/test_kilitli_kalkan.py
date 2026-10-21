"""Amendment 22: target-locking shield (eland_rl.kilitli_kalkan), in the environment with the measured lags."""
import numpy as np

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.kilitli_kalkan import KilitliKalkan
from eland_rl.pilots import shield
from eland_rl.scene import Scene


def sahne(cls=2, size=(120.0, 120.0), res=0.1):
    w, h = int(size[0] / res), int(size[1] / res)
    return Scene(np.full((h, w), cls, np.uint8), size, name=f'duz{cls}')


def boya(sc, x0, x1, y0, y1, cls):
    H, W = sc.mask.shape
    c0, c1 = int((x0 / sc.size[0] + 0.5) * W), int((x1 / sc.size[0] + 0.5) * W)
    r0, r1 = int((0.5 - y1 / sc.size[1]) * H), int((0.5 - y0 / sc.size[1]) * H)
    sc.mask[r0:r1, c0:c1] = cls
    return sc


def ucur(sc, kalkan, h=8.0, yaw=0.0):
    """Always-descend 'policy' behind a shield, nominal (lagged) dynamics; the episode's outcome."""
    env = LandingEnv([sc], EnvConfig(obs_mode='sem_depth_sora', randomise_dynamics=False, max_t=30.0,
                                     **REWARD_PRESETS['zemin_v3']))
    obs, _ = env.reset(seed=0, options={'start': (0.0, 0.0, h, yaw)})
    kk = KilitliKalkan()
    while True:
        pos, R = env.veh.delayed_pose()
        if kalkan == 'eski':
            a = shield(9, obs, pos[2], 10.0)[0]
        else:
            a = kk(9, obs, pos[2], env.veh.t, pos, R, env.veh.pos[:2], env.veh.yaw, env.cam.rays)[0]
        obs, _, done, trunc, info = env.step(a)
        if done or trunc:
            return info


def test_ustte_karisilmaz():
    kk = KilitliKalkan()
    o = np.zeros((3, 128, 128), np.float32)
    assert kk(9, o, 12.0, 0.0, np.zeros(3), np.eye(3), np.zeros(2), 0.0, None) == (9, False)


def test_genis_cim_alana_iner():
    # asphalt everywhere, grass 1.5..6 m to the right (yaw 0: right = -y), start 8 m over the asphalt
    info = ucur(boya(sahne(2), -3, 3, -6, -1.5, 0), 'kilitli')
    assert info['outcome'] == 'safe_landing' and info['zemin_success']


def test_dar_seride_iner():
    # a 1.2 m grass strip 2 m to the right: the strip's middle, not its edge, is the target
    info = ucur(boya(sahne(2), -10, 10, -3.2, -2.0, 0), 'kilitli')
    assert info['outcome'] == 'safe_landing' and info['zemin_success']


def test_guvenli_yer_yoksa_bekler():
    info = ucur(sahne(2), 'kilitli')
    assert info['outcome'] == 'timeout'                 # holds, never lands on the asphalt
