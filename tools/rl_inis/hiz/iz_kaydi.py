"""Ayni tohum ve ayni eylemlerle bolumleri kos, her adimin gozlem/odul/bilgi ozetini kaydet.

    python iz_kaydi.py <sahne_listesi> <cikti.npz>   (sys.path hangi eland_rl'yi gosterirse onu kullanir)
"""
import hashlib
import sys
import time

import numpy as np

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list

KOLLAR = {
    'A1_P0': {},
    'PA': dict(sem_source='pred'),
    'PB': dict(sem_source='pred', depth_mode='elev'),
    'PC': dict(sem_source='pred', sora_elev_tau=0.12),
    'PD': dict(sem_source='pred', depth_mode='elev', sora_elev_tau=0.12),
    'A2b': dict(shield_m=10.0),
}
scenes = load_list(sys.argv[1], dist_cell_m=0.25)
out = {}
for ad, ek in KOLLAR.items():
    env = LandingEnv(scenes, EnvConfig(obs_mode='sem_depth_sora', **ek, **REWARD_PRESETS['sora_v1']))
    rng = np.random.default_rng(7)
    h, rows, n = hashlib.sha256(), [], 0
    t0 = time.perf_counter()
    for ep in range(40):
        obs, info = env.reset(seed=1000 + ep)
        h.update(obs.tobytes())
        done = False
        while not done:
            # mostly descend so episodes reach the ground; some lateral and halt
            a = 9 if rng.random() < 0.55 else int(rng.integers(0, 9))
            obs, r, done, _, info = env.step(a)
            h.update(obs.tobytes())
            rows.append((r, info['r_shape'], info['action'], float(info['shielded'])))
            n += 1
        rows.append((float(info.get('sora_success', -1)), float(info['t']), float(info['landing_xy'][0]),
                     float(info['landing_xy'][1])))
        h.update(info['outcome'].encode())
    out[ad + '_iz'] = np.array(rows)
    out[ad + '_ozet'] = np.frombuffer(h.digest(), np.uint8)
    print(f'{ad}: {n} adim, {(time.perf_counter() - t0) / n * 1e3:.2f} ms/adim', flush=True)
np.savez(sys.argv[2], **out)
