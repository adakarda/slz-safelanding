"""Gorus kahini zemin kuralinda dogru calisiyor mu? Ayni baslangiclarda sora_v1 ve zemin_v1 kahinleri."""
import collections
import sys

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.evaluate import run
from eland_rl.pilots import view_oracle
from eland_rl.scenes import load_list

sc = load_list(sys.argv[1], dist_cell_m=0.25)[:6]
for preset in ('sora_v1', 'zemin_v1'):
    env = LandingEnv(sc, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', **REWARD_PRESETS[preset]))
    c, cls = collections.Counter(), collections.Counter()
    for i in range(len(sc)):
        for k in range(5):
            info, _, _ = run(env, lambda o: view_oracle(env), i, k)
            c[info['outcome']] += 1
            cls[info['landing_class']] += 1
    print(preset, dict(c), 'inis sinifi', dict(sorted(cls.items())))
