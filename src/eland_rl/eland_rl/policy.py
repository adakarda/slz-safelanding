"""The policy network of Bartolomei et al., IROS 2022 (Fig. 3), for Stable-Baselines3.

Shared trunk: Conv 8x8/4, Conv 4x4/2, Conv 3x3/1, FC 128 (ReLU throughout).
Actor: three FC 64. Critic: two FC 32. The paper gives kernel sizes and
strides but not channel counts; 32/64/64 are assumed (the Atari "Nature CNN"
the kernel/stride pattern comes from). docs/onkayit/rl_f0_onkayit.md section 4.
"""
import gymnasium as gym
import torch
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from torch import nn


class PaperCNN(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 128):
        super().__init__(observation_space, features_dim)
        c = observation_space.shape[0]
        self.cnn = nn.Sequential(
            nn.Conv2d(c, 32, 8, stride=4), nn.ReLU(),
            nn.Conv2d(32, 64, 4, stride=2), nn.ReLU(),
            nn.Conv2d(64, 64, 3, stride=1), nn.ReLU(),
            nn.Flatten())
        with torch.no_grad():
            n = self.cnn(torch.zeros(1, *observation_space.shape)).shape[1]
        self.fc = nn.Sequential(nn.Linear(n, features_dim), nn.ReLU())

    def forward(self, obs):
        return self.fc(self.cnn(obs))


POLICY_KWARGS = dict(
    features_extractor_class=PaperCNN,
    features_extractor_kwargs=dict(features_dim=128),
    net_arch=dict(pi=[64, 64, 64], vf=[32, 32]),
    normalize_images=False,
    share_features_extractor=True,
)
