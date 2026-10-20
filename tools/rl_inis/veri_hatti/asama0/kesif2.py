"""Asama 0 olcumleri: zip'ten salt okuma. manifest, EXIF/XMP, maske turu ve boyutu, eslesme, GPS kumeleri."""
import collections
import csv
import io
import math
import re
import sys
import zipfile

import numpy as np
from PIL import Image

z = zipfile.ZipFile(sys.argv[1])
names = set(z.namelist())
P = 'messi_rl/'
rows = list(csv.DictReader(io.TextIOWrapper(z.open(P + 'manifest.csv'), 'utf-8')))
print('manifest satir:', len(rows), '| benzersiz id:', len({r['id'] for r in rows}))
print('sutunlar:', list(rows[0].keys()))


def ozet(key, f=float):
    v = np.array([f(r[key]) for r in rows if r[key] not in ('', None)])
    return f'{key}: n={len(v)} min={v.min():.2f} p50={np.median(v):.2f} max={v.max():.2f}'


for k in ('rel_alt_m', 'abs_alt_m', 'gsd_cm', 'gimbal_pitch_deg', 'odak_mm', 'w', 'h'):
    print(' ', ozet(k))
print('  w x h:', collections.Counter((r['w'], r['h']) for r in rows))
print('  kamera:', collections.Counter(r['kamera'] for r in rows))
print('  etiket/bolge/tur:', collections.Counter((r['etiket'], r['bolge'], r['tur']) for r in rows))
print('  v3_kullanim:', collections.Counter(r['v3_kullanim'] for r in rows))
alt = np.array([float(r['rel_alt_m']) for r in rows])
print('  irtifa histogram (m):', np.histogram(alt, bins=[80, 85, 90, 95, 100, 105, 110, 115, 121])[0].tolist())

# dosya varligi ve eslesme
eksik = collections.Counter()
for r in rows:
    for k in ('img', 'mask_raw16', 'mask_sora7'):
        if P + r[k] not in names:
            eksik[k] += 1
print('\nmanifestte olup zipte olmayan:', dict(eksik))
listed = {P + r[k] for r in rows for k in ('img', 'mask_raw16', 'mask_sora7')}
extra = sorted(n for n in names if not n.endswith('/') and n not in listed and not n.endswith(('.csv', '.md')))
print('zipte olup manifestte olmayan:', extra[:10], len(extra))

# boyut kontrolu (sadece basliklar)
bad = 0
for r in rows:
    sz = set()
    for k in ('img', 'mask_raw16', 'mask_sora7'):
        if P + r[k] in names:
            with Image.open(io.BytesIO(z.read(P + r[k]))) as im:
                sz.add(im.size)
                if k != 'img':
                    mode = im.mode
    if len(sz) != 1 or (int(r['w']), int(r['h'])) not in sz:
        bad += 1
print('boyut uyusmayan kare:', bad, '| maske modu ornegi:', mode)

# EXIF / XMP (173 JPG)
ex = []
for r in rows:
    n = P + r['img']
    if n not in names:
        continue
    b = z.read(n)
    im = Image.open(io.BytesIO(b))
    e = im.getexif()
    sub = e.get_ifd(0x8769)
    xmp = b[:200000].decode('latin-1')
    m = re.search(r'RelativeAltitude="([-+0-9.]+)"', xmp)
    ex.append((float(r['rel_alt_m']), float(m.group(1)) if m else math.nan, float(sub.get(0x920A, math.nan)),
               sub.get(0xA405), e.get(0x0110), im.size))
ex = np.array([(a, b, c, d or 0) for a, b, c, d, _, _ in ex])
print(f'\nEXIF {len(ex)} JPG: model {set(x[4] for x in [])}')
print(f'  FocalLength: {np.unique(ex[:, 2])}  | FocalLengthIn35mm: {np.unique(ex[:, 3])}')
f35 = np.unique(ex[:, 3])[0]
print(f'  sensor genisligi = 36 x f / f35 = {36 * ex[0, 2] / f35:.2f} mm')
d = ex[:, 1] - ex[:, 0]
print(f'  XMP RelativeAltitude - manifest rel_alt: ortalama {np.nanmean(d):+.2f} m, max |fark| {np.nanmax(np.abs(d)):.2f} m')

# GPS: ucus (seq) basina merkez ve yayilim, ucuslar arasi mesafe
g = collections.defaultdict(list)
for r in rows:
    g[r['seq']].append((float(r['lat']), float(r['lon']), float(r['rel_alt_m'])))
lat0 = np.mean([float(r['lat']) for r in rows])
k_lat, k_lon = 111_320.0, 111_320.0 * math.cos(math.radians(lat0))
cent = {}
print('\nucus basina GPS (m, ortak orijinden):')
for s, v in sorted(g.items()):
    v = np.array(v)
    x, y = (v[:, 1] - v[:, 1].mean()) * k_lon, (v[:, 0] - v[:, 0].mean()) * k_lat
    cent[s] = (v[:, 0].mean() * k_lat, v[:, 1].mean() * k_lon)
    print(f'  {s:32s} n={len(v):3d} yayilim(m) x={np.ptp(x):6.1f} y={np.ptp(y):6.1f} irtifa {v[:, 2].min():.0f}-{v[:, 2].max():.0f}')
ks = sorted(cent)
D = np.array([[math.dist(cent[a], cent[b]) for b in ks] for a in ks])
print('\nucus merkezleri arasi en yakin komsu (m):')
for i, a in enumerate(ks):
    j = np.argsort(D[i])[1]
    print(f'  {a:32s} -> {ks[j]:32s} {D[i, j]:7.1f} m')
