"""Gazebo demosundaki inisler: 5 m'ye inilen nokta, oradaki sinif, SORA uygunlugu ve en yakin cim.

    python izle_inis.py <izle klasoru>
"""
import csv
import math
import sys

import numpy as np

from eland_rl.scene import Scene

NAMES = ['yumusak (cim/toprak)', 'sert (kaldirim)', 'asfalt/agac', 'bina', 'su', 'arac', 'insan', 'bilinmeyen']
sc = Scene.from_messi('/home/arda/v3_test/foto/fotoo/DJI_0097.JPG', '/home/arda/v3_test/maske/fotomask/DJI_0097.png',
                      size_m=(64.02, 42.68))
sc.dist_cell = 0.1
rows = list(csv.DictReader(open(sys.argv[1] + '/politika.csv')))
# her inis: z_cam 5 m'nin altina ilk indigi an (yeniden kalkislar ayri inis)
landings, low = [], False
for r in rows:
    z = float(r['z_cam'])
    if z < 5.0 and not low:
        landings.append(r)
    low = z < 5.0
soft = (sc.mask == 0)
H, W = sc.mask.shape
for i, r in enumerate(landings):
    x, y = float(r['x']), float(r['y'])
    cls = int(sc.classes_at(np.array([x]), np.array([y]))[0])
    sora_ok = sc.is_sora_safe(x, y, 3.0)
    # en yakin cim pikseli ve en yakin SORA-uygun cim noktasi
    vv, uu = np.nonzero(soft)
    gx = (uu + 0.5) / W * sc.size[0] - sc.size[0] / 2
    gy = sc.size[1] / 2 - (vv + 0.5) / H * sc.size[1]
    d = np.hypot(gx - x, gy - y)
    safe, _, _ = sc._sora_grid(3.0)
    gh, gw = safe.shape
    sv, su = np.nonzero(safe)
    sx = (su + 0.5) / gw * sc.size[0] - sc.size[0] / 2
    sy = sc.size[1] / 2 - (sv + 0.5) / gh * sc.size[1]
    cell_soft = sc.classes_at(sx, sy) == 0
    ds = np.hypot(sx[cell_soft] - x, sy[cell_soft] - y)
    print(f'inis {i + 1}: t_sim {float(r["t_sim"]):.1f} s, nokta ({x:.1f}, {y:.1f}) m -> {NAMES[cls]}; '
          f'SORA 3 m uygun: {sora_ok}; en yakin cim {d.min():.1f} m; en yakin SORA-uygun cim '
          f'{ds.min() if len(ds) else math.inf:.1f} m; tampona bakmadan hazard uzakligi {sc.hazard_distance(x, y):.1f} m')
print(f'fotoda cim payi %{100 * soft.mean():.1f}, SORA-uygun alan payi %{100 * safe.mean():.1f}, '
      f'SORA-uygun alanin icinde cim payi %{100 * (sc.classes_at(sx, sy) == 0).mean():.1f}')
