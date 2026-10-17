"""Amendment 10 encoders: they read the observation as the environment writes it, and plug into SB3."""
import gymnasium as gym
import numpy as np
import pytest
import torch

from eland_rl.policy import ENCODERS, POLICY_KWARGS, one_hot, policy_kwargs

SPACE = gym.spaces.Box(0.0, 1.0, (3, 128, 128), np.float32)


def test_one_hot_recovers_the_classes():
    cls = torch.randint(0, 8, (2, 128, 128))
    obs = torch.stack([cls.float() / 7, torch.rand(2, 128, 128), torch.rand(2, 128, 128)], 1)
    oh = one_hot(obs)
    assert oh.shape == (2, 8, 128, 128)
    assert torch.equal(oh.argmax(1), cls) and torch.all(oh.sum(1) == 1)


@pytest.mark.parametrize('name', sorted(ENCODERS))
def test_encoder_output(name):
    cls, dim = ENCODERS[name]
    enc = cls(SPACE, dim)
    out = enc(torch.rand(4, 3, 128, 128))
    assert out.shape == (4, dim) and torch.isfinite(out).all()


def test_paper_kwargs_unchanged():
    assert policy_kwargs('paper') == POLICY_KWARGS


@pytest.mark.parametrize('name', ['iki_kol', 'impala'])
def test_ppo_builds_and_acts(name):
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import DummyVecEnv

    class Dummy(gym.Env):
        observation_space = SPACE
        action_space = gym.spaces.Discrete(10)

        def reset(self, *, seed=None, options=None):
            return self.observation_space.sample(), {}

        def step(self, a):
            return self.observation_space.sample(), 0.0, True, False, {}

    m = PPO('MlpPolicy', DummyVecEnv([Dummy]), policy_kwargs=policy_kwargs(name), n_steps=8, batch_size=8,
            device='cpu', verbose=0)
    a, _ = m.predict(SPACE.sample(), deterministic=True)
    assert 0 <= int(a) < 10
