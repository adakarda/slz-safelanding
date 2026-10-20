"""Check the extracted MESSI package against its manifest; SORA-safe share on a sample."""
import csv
import glob
import os

import numpy as np
from PIL import Image

from eland_rl.scene import Scene

R = '/home/arda/eland_veri/rl/messi_rl'
man = list(csv.DictReader(open(f'{R}/manifest.csv')))
pngs = set(os.path.relpath(p, R) for p in glob.glob(f'{R}/masks_sora7/**/*.png', recursive=True))
listed = set(m['mask_sora7'] for m in man)
print('manifest', len(man), 'maske dosyasi', len(pngs), 'manifestte olup dosyasi yok', len(listed - pngs),
      'dosyasi olup manifestte yok', sorted(pngs - listed)[:3])
from collections import Counter
print('etiket', Counter(m['etiket'] for m in man), 'tur', Counter((m['etiket'], m['tur']) for m in man))
alt = np.array([float(m['rel_alt_m']) for m in man])
print('irtifa', alt.min(), np.median(alt), alt.max())
rng = np.random.default_rng(0)
for m in [man[i] for i in sorted(rng.choice(len(man), 6, replace=False))] + [x for x in man if x['etiket'] == 'test'][:2]:
    mk = np.array(Image.open(f"{R}/{m['mask_sora7']}"))
    g = float(m['gsd_cm']) / 100
    sc = Scene(mk, (mk.shape[1] * g, mk.shape[0] * g), name=m['ad'])
    safe, _, _ = sc._sora_grid(3.0)
    print(f"{m['etiket']:8s} {m['bolge']:8s} {m['tur']:7s} {m['ad']}: {sc.size[0]:.0f}x{sc.size[1]:.0f} m, "
          f"degerler {sorted(np.unique(mk).tolist())}, SORA-guvenli %{100 * safe.mean():.1f}")
