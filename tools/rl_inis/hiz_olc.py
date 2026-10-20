"""F1: environment speed on the five local photos (development scenes only, not results)."""
import collections
import glob
import os
import time

import numpy as np

from eland_rl.env import EnvConfig, LandingEnv
from eland_rl.scene import Scene

FOTO = sorted(glob.glob('/home/arda/v3_test/foto/fotoo/*.JPG'))
t0 = time.time()
sahneler = []
for f in FOTO:
    ad = os.path.basename(f)[:-4]
    s = Scene.from_messi(f, f'/home/arda/v3_test/maske/fotomask/{ad}.png')
    sahneler.append(s)
    pay = np.bincount(s.mask.ravel(), minlength=8) / s.mask.size
    print(f'{ad}: {s.size[0]:.1f} x {s.size[1]:.1f} m, guvenli pay {pay[0] + pay[1]:.2f}, '
          f'sinif paylari {np.round(pay, 3).tolist()}')
print(f'yukleme {time.time() - t0:.1f} s')

env = LandingEnv(sahneler, EnvConfig())
rng = np.random.default_rng(0)
for ad, politika in (('rastgele', lambda: int(rng.integers(10))), ('duz_inis', lambda: 9)):
    env.reset(seed=0)
    sonuc = collections.Counter()
    n, t0 = 0, time.time()
    while n < 4000:
        _, _, bitti, _, info = env.step(politika())
        n += 1
        if bitti:
            sonuc[info['outcome']] += 1
            env.reset()
    dt = time.time() - t0
    print(f'{ad}: {n / dt:.0f} adim/s (tek cekirdek), sonuclar {dict(sonuc)}')
