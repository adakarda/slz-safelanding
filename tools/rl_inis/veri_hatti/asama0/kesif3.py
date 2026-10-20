"""Asama 0, ikinci kisim: maske piksel kontrolleri (orneklem), sinif dagilimi, sahne kumeleri. Salt okuma."""
import collections
import csv
import hashlib
import io
import math
import sys
import zipfile

import numpy as np
from PIL import Image

z = zipfile.ZipFile(sys.argv[1])
P = 'messi_rl/'
rows = list(csv.DictReader(io.TextIOWrapper(z.open(P + 'manifest.csv'), 'utf-8')))
M16 = {0: 7, 1: 5, 2: 3, 3: 3, 4: 3, 5: 6, 6: 3, 7: 0, 8: 3, 9: 0, 10: 3, 11: 2, 12: 2, 13: 5, 14: 1, 15: 4}
lut = np.full(256, 255, np.uint8)
for k, v in M16.items():
    lut[k] = v
SORA = ['safe_soft', 'safe_hard', 'terrain_hazard', 'structure', 'water', 'vehicle_animal', 'person', 'unknown']
RAW = ['unidentified', 'bicycle', 'building', 'wall', 'misc-object', 'person', 'pole', 'bare-soil', 'awning', 'grass',
       'stairs', 'asphalt', 'tree', 'car', 'sidewalk', 'pool']

# 1) butun maskelerin modu (sadece baslik)
modes = collections.Counter()
for n in z.namelist():
    if n.endswith('.png'):
        with Image.open(io.BytesIO(z.read(n))) as im:
            modes[(n.split('/')[1], im.mode)] += 1
print('maske modlari:', dict(modes))

# 2) fazladan dosya
a = z.read(P + 'masks_sora7/trainval/Agamim/Descend/100_0042/HYPERLAPSE_0087(1).png')
bn = P + 'masks_sora7/trainval/Agamim/Descend/100_0042/HYPERLAPSE_0087.png'
b = z.read(bn) if bn in z.namelist() else b''
print('HYPERLAPSE_0087(1).png ile HYPERLAPSE_0087.png bayt olarak ayni mi:', a == b,
      '| manifestte HYPERLAPSE_0087 var mi:', any(r['ad'] == 'HYPERLAPSE_0087' and r['seq'].endswith('0042') for r in rows))

# 3) orneklem: her ucustan 2 kare (ilk ve son), tam piksel
by = collections.defaultdict(list)
for r in rows:
    by[r['seq']].append(r)
sample = [v[i] for v in by.values() for i in (0, len(v) - 1)]
raw_tot = np.zeros(256, np.int64)
mism, uniq_raw, uniq_s7, pdiff = 0, set(), set(), []
for r in sample:
    m16 = np.asarray(Image.open(io.BytesIO(z.read(P + r['mask_raw16']))))
    m7 = np.asarray(Image.open(io.BytesIO(z.read(P + r['mask_sora7']))))
    uniq_raw |= set(np.unique(m16).tolist())
    uniq_s7 |= set(np.unique(m7).tolist())
    raw_tot += np.bincount(m16.ravel(), minlength=256)
    mism += int((lut[m16] != m7).sum())
    share = np.bincount(m7.ravel(), minlength=8)[:8] / m7.size
    man = np.array([float(r['p_' + c]) for c in SORA])
    pdiff.append(np.abs(share - man).max())
print(f'\norneklem {len(sample)} kare (her ucustan ilk+son):')
print('  raw16 degerleri:', sorted(uniq_raw), '| sora7 degerleri:', sorted(uniq_s7))
print('  README tablosuyla raw16 -> sora7 uyusmayan piksel:', mism)
print(f'  manifest p_* ile tam piksel payi farki: en fazla {max(pdiff):.4f}')
tot = raw_tot[:16] / raw_tot.sum()
print('  raw16 piksel paylari (orneklem):', {RAW[i]: round(float(tot[i]) * 100, 2) for i in range(16) if tot[i] > 0})

# 4) butun veri: manifest p_* (1/8 ornekleme) ile SORA sinif dagilimi
p = np.array([[float(r['p_' + c]) for c in SORA] for r in rows])
print('\nSORA 7 sinif paylari (716 kare, piksel ortalamasi %):', {c: round(float(x) * 100, 2) for c, x in zip(SORA, p.mean(0))})
print('  sinifi iceren kare sayisi:', {c: int((p[:, i] > 0).sum()) for i, c in enumerate(SORA)})
for et in ('trainval', 'test'):
    q = p[[r['etiket'] == et for r in rows]]
    print(f'  {et}: n={len(q)} safe_soft+hard %{q[:, :2].sum(1).mean() * 100:.1f}, person kareleri {int((q[:, 6] > 0).sum())}, '
          f'vehicle kareleri {int((q[:, 5] > 0).sum())}, water kareleri {int((q[:, 4] > 0).sum())}')

# 5) sahne kumeleri: ucus merkezleri, 100 m'deki iz (128.6 x 85.7 m) ile ortusme esigi
lat0 = np.mean([float(r['lat']) for r in rows])
kx, ky = 111_320.0 * math.cos(math.radians(lat0)), 111_320.0
pts = {s: (np.mean([float(r['lon']) for r in v]) * kx, np.mean([float(r['lat']) for r in v]) * ky) for s, v in by.items()}
ks = sorted(pts)
print('\nsecili ucuslar arasi merkez mesafesi (m):')
sel = ['Agamim/Descend/100_000' + i for i in '12346']
print('  ' + ' '.join(f'{s[-4:]:>7s}' for s in sel))
for a_ in sel:
    print(f'  {a_[-4:]} ' + ' '.join(f'{math.dist(pts[a_], pts[b_]):7.1f}' for b_ in sel))
for esik in (60, 86, 129):
    parent = {s: s for s in ks}

    def f(s):
        while parent[s] != s:
            s = parent[s]
        return s
    for i, a_ in enumerate(ks):
        for b_ in ks[i + 1:]:
            if math.dist(pts[a_], pts[b_]) < esik:
                parent[f(a_)] = f(b_)
    cl = collections.defaultdict(list)
    for s in ks:
        cl[f(s)].append(s.split('/', 1)[1] if s.startswith('Agamim') else s)
    print(f'\nkume esigi {esik} m -> {len(cl)} kume:')
    for v in cl.values():
        print('   ', sorted(v))
