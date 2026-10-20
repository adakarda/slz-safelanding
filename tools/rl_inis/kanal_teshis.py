"""Channel pilot: outcome breakdown, and how often the channel's centre agrees with the truth, by altitude."""
import collections
import sys

import numpy as np

sys.argv = [sys.argv[0], sys.argv[1]]
exec(open('/home/arda/rl_inis/gorus_kahini.py').read().split("for name, act in (('duz_inis'")[0])  # env, helpers
from eland_rl.camera import ground_hits, sora_channel  # noqa: E402
exec(open('/home/arda/rl_inis/gorus_kahini.py').read().split('from eland_rl.camera import sora_channel  # noqa: E402')[1].split('ss, R = [], []')[0])
oc = collections.Counter()
agree = collections.defaultdict(lambda: np.zeros((2, 2), int))
for si in range(len(scenes)):
    for k in range(15):
        obs, _ = env.reset(seed=k, options={'scene_index': si})
        while True:
            pos, R = env.veh.delayed_pose()
            sem = np.round(obs[0] * 7).astype(np.uint8)
            ch = sora_channel(sem, pos[2])
            X, Y, _ = ground_hits(np.array([[0.0, 0.0, -1.0]]), pos, R)
            truth = env.scene.is_sora_safe(X[0], Y[0])
            band = '5-10' if pos[2] < 10 else '10-18' if pos[2] < 18 else '18-30'
            agree[band][int(truth), int(ch[62:66, 62:66].all())] += 1
            obs, r, done, _, info = env.step(channel_pilot(obs))
            if done:
                break
        oc[info['outcome']] += 1
print('kanal pilotu sonuclari', dict(oc))
for band, m in agree.items():
    tn, fp, fn, tp = m[0, 0], m[0, 1], m[1, 0], m[1, 1]
    print(f'irtifa {band} m: kanal "guvenli" dediginde dogru %{100 * tp / max(tp + fp, 1):.0f} ({tp}/{tp + fp}), '
          f'gercek guvenlinin kanalda yakalanan payi %{100 * tp / max(tp + fn, 1):.0f} ({tp}/{tp + fn})')
