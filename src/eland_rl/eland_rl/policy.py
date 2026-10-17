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


# ------------------------------------------------------- amendment 10: other encoders
# Same heads as the paper; only the trunk changes. Channel 0 is class / 7, channel 1 depth / 40 m,
# channel 2 (if any) the SORA / target mask.
N_CLASSES = 8


def one_hot(obs):
    """The classes of channel 0 as one-hot planes, (B, 8, H, W): no false order between classes."""
    cls = torch.round(obs[:, 0] * (N_CLASSES - 1)).long().clamp(0, N_CLASSES - 1)
    return nn.functional.one_hot(cls, N_CLASSES).permute(0, 3, 1, 2).float()


def nature_stack(c, widths=(32, 64, 64)):
    return nn.Sequential(
        nn.Conv2d(c, widths[0], 8, stride=4), nn.ReLU(),
        nn.Conv2d(widths[0], widths[1], 4, stride=2), nn.ReLU(),
        nn.Conv2d(widths[1], widths[2], 3, stride=1), nn.ReLU(),
        nn.Flatten())


class OneHotPaperCNN(BaseFeaturesExtractor):
    """The paper's trunk, but the classes enter as one-hot planes (early fusion, as in the paper)."""

    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 128):
        super().__init__(observation_space, features_dim)
        c = observation_space.shape[0]
        self.cnn = nature_stack(N_CLASSES + c - 1)
        with torch.no_grad():
            n = self.cnn(self._in(torch.zeros(1, *observation_space.shape))).shape[1]
        self.fc = nn.Sequential(nn.Linear(n, features_dim), nn.ReLU())

    def _in(self, obs):
        return torch.cat([one_hot(obs), obs[:, 1:]], 1)

    def forward(self, obs):
        return self.fc(self.cnn(self._in(obs)))


class TwoBranchCNN(BaseFeaturesExtractor):
    """Late fusion: semantics and geometry in separate branches, joined before the FC layer.
    Semantic branch: one-hot classes + the SORA / target mask, the paper's conv stack.
    Geometry branch: depth alone, a narrower stack. Plus the height as one number (mean depth of
    the centre 4x4), which the paper's net has to read off the depth image."""

    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 128):
        super().__init__(observation_space, features_dim)
        self.has_mask = observation_space.shape[0] >= 3
        self.sem = nature_stack(N_CLASSES + int(self.has_mask))
        self.geo = nature_stack(1, (16, 32, 32))
        with torch.no_grad():
            z = torch.zeros(1, *observation_space.shape)
            n = self.sem(self._sem_in(z)).shape[1] + self.geo(z[:, 1:2]).shape[1] + 1
        self.fc = nn.Sequential(nn.Linear(n, features_dim), nn.ReLU())

    def _sem_in(self, obs):
        oh = one_hot(obs)
        return torch.cat([oh, obs[:, 2:3]], 1) if self.has_mask else oh

    def forward(self, obs):
        height = obs[:, 1, 62:66, 62:66].mean((1, 2)).unsqueeze(1)
        return self.fc(torch.cat([self.sem(self._sem_in(obs)), self.geo(obs[:, 1:2]), height], 1))


class _Residual(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.c1 = nn.Conv2d(c, c, 3, padding=1)
        self.c2 = nn.Conv2d(c, c, 3, padding=1)

    def forward(self, x):
        return x + self.c2(torch.relu(self.c1(torch.relu(x))))


class ImpalaCNN(BaseFeaturesExtractor):
    """IMPALA encoder (Espeholt et al. 2018): three stages of conv 3x3, max-pool 3x3/2 and two
    residual blocks. It generalises better than the Nature CNN in CoinRun/Procgen (Cobbe et al.
    2019, 2020). Input: one-hot classes, the other channels and two coordinate planes (CoordConv,
    Liu et al. 2018), so the filters know where in the image they are."""

    def __init__(self, observation_space: gym.spaces.Box, features_dim: int = 256, widths=(16, 32, 32)):
        super().__init__(observation_space, features_dim)
        c, h, w = observation_space.shape
        ys, xs = torch.meshgrid(torch.linspace(-1, 1, h), torch.linspace(-1, 1, w), indexing='ij')
        self.register_buffer('coords', torch.stack([xs, ys])[None])
        layers, cin = [], N_CLASSES + c - 1 + 2
        for width in widths:
            layers += [nn.Conv2d(cin, width, 3, padding=1), nn.MaxPool2d(3, 2, padding=1),
                       _Residual(width), _Residual(width)]
            cin = width
        self.cnn = nn.Sequential(*layers, nn.ReLU(), nn.Flatten())
        with torch.no_grad():
            n = self.cnn(self._in(torch.zeros(1, c, h, w))).shape[1]
        self.fc = nn.Sequential(nn.Linear(n, features_dim), nn.ReLU())

    def _in(self, obs):
        return torch.cat([one_hot(obs), obs[:, 1:], self.coords.expand(obs.shape[0], -1, -1, -1)], 1)

    def forward(self, obs):
        return self.fc(self.cnn(self._in(obs)))


#: name -> (extractor, features_dim); 'paper' is POLICY_KWARGS unchanged.
ENCODERS = {
    'paper': (PaperCNN, 128),
    'paper_onehot': (OneHotPaperCNN, 128),
    'iki_kol': (TwoBranchCNN, 128),
    'impala': (ImpalaCNN, 256),
}


def policy_kwargs(encoder='paper'):
    cls, dim = ENCODERS[encoder]
    return {**POLICY_KWARGS, 'features_extractor_class': cls, 'features_extractor_kwargs': dict(features_dim=dim)}
