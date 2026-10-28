"""reset(seed=k) alone fixes an episode: a fresh environment and one that has already flown other episodes give
the same trace (evaluate.py flies every scene x start through one environment)."""
import numpy as np
import pytest

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.kilitli_kalkan import KilitliKalkan
from eland_rl.pilots import channel_pilot
from eland_rl.scene import Scene


def blob_scene(seed, size=(120.0, 90.0), res=0.25):
    """Grass with random patches of hard ground, road, buildings and people, so a pilot has to slide."""
    rng = np.random.default_rng(seed)
    w, h = int(size[0] / res), int(size[1] / res)
    mask = np.zeros((h, w), np.uint8)
    for cls, n, r in ((1, 12, 30), (2, 8, 25), (3, 10, 20), (6, 15, 3)):
        for _ in range(n):
            cx, cy = rng.integers(w), rng.integers(h)
            mask[max(cy - r, 0):cy + r, max(cx - r, 0):cx + r] = cls
    return Scene(mask, size, name=f'blob{seed}', dist_cell_m=0.25)


CONFIGS = {
    'final': dict(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', diag_actions=True, shield_m=10.0,
                  gimbal=True, **REWARD_PRESETS['zemin_v3']),
    'training': dict(max_t=30.0, randomise_dynamics=True, obs_mode='sem_depth_sora', diag_actions=True, mirror=True,
                     shield_m=10.0, kanallar=('risk', 'hedef', 'hafiza'), **REWARD_PRESETS['zemin_v3']),
}


def fly(env, k, scene_index):
    """Trace of one episode: channel pilot behind the locking shield (the final candidate's loop, no network)."""
    kk = KilitliKalkan(below_m=10.0)
    obs, info = env.reset(seed=k, options={'scene_index': scene_index})
    trace = [obs.copy(), np.array(info['start'])]
    while True:
        pos, R = env.kamera_pozu()
        a = kk(channel_pilot(obs), obs, pos[2], env.veh.t, pos, R, env.veh.pos[:2], env.veh.yaw, env.cam.rays)[0]
        obs, r, done, trunc, info = env.step(a)
        trace += [a, obs.copy(), env.veh.pos.copy(), r]
        if done or trunc:
            trace += [info['outcome'], info['t']]
            return trace


def same(a, b):
    return len(a) == len(b) and all(np.array_equal(x, y) for x, y in zip(a, b))


@pytest.mark.parametrize('name', sorted(CONFIGS))
def test_reset_seed_fixes_the_episode(name):
    scenes = [blob_scene(1), blob_scene(2)]
    shared = LandingEnv(scenes, EnvConfig(**CONFIGS[name]))
    for k in (3, 4):                                        # other episodes first, on both scenes
        fly(shared, k, 0)
        fly(shared, k, 1)
    for k in (1, 5, 7):
        fresh = fly(LandingEnv(scenes, EnvConfig(**CONFIGS[name])), k, 1)
        assert len(fresh) > 10                              # the episode actually flew
        assert same(fresh, fly(shared, k, 1)), f'start {k}: the shared environment flew another episode'


def test_scene_order_does_not_matter():
    """Scene caches (target grids, hazard distances) built by earlier episodes do not change later ones."""
    cfg = EnvConfig(**CONFIGS['final'])
    a = fly(LandingEnv([blob_scene(1), blob_scene(2)], cfg), 5, 1)
    warm = [blob_scene(1), blob_scene(2)]
    env = LandingEnv(warm, cfg)
    fly(env, 5, 0)
    assert same(a, fly(env, 5, 1))
