"""Amendment 7: pick the Depth Anything elevation threshold tau on the TRAINING flights only.

Landable ground (MESSI raw: bare soil 7, grass 9, sidewalk 14) against raised things
(building 2, wall 3, awning 8, tree 12). tau maximises Youden's J = TPR - FPR, where a pixel
is called 'raised' when its relative elevation exceeds tau. Test flight 100_0004 is not used.
"""
import csv
import os

import cv2
import numpy as np

R = '/home/arda/eland_veri/rl/messi_rl'
E = '/home/arda/eland_veri/rl/messi_ds4/elev'
TEST_SEQ = 'Agamim/Descend/100_0004'
man = [m for m in csv.DictReader(open(f'{R}/manifest.csv')) if os.path.exists(f"{R}/{m['img']}")]
ground, raised = [], []
rng = np.random.default_rng(0)
for m in man:
    if m['seq'] == TEST_SEQ:
        continue
    e = cv2.imread(f"{E}/{m['id'].replace('/', '__')}.png", cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    raw = cv2.imread(f"{R}/{m['mask_raw16']}", cv2.IMREAD_UNCHANGED)
    raw = cv2.resize(raw, (e.shape[1], e.shape[0]), interpolation=cv2.INTER_NEAREST)
    g, r = e[np.isin(raw, [7, 9, 14])], e[np.isin(raw, [2, 3, 8, 12])]
    ground.append(rng.choice(g, min(4000, len(g)), replace=False) if len(g) else g)
    raised.append(rng.choice(r, min(4000, len(r)), replace=False) if len(r) else r)
g, r = np.concatenate(ground), np.concatenate(raised)
taus = np.linspace(0.02, 0.9, 89)
J = [(r > t).mean() - (g > t).mean() for t in taus]
k = int(np.argmax(J))
print(f'egitim ucuslari: {len(ground)} kare, zemin {len(g)} / yukseltilmis {len(r)} ornek piksel')
print(f'tau = {taus[k]:.2f}: yukseltilmisi yakalama %{100 * (r > taus[k]).mean():.1f}, '
      f'zemini yanlis isaretleme %{100 * (g > taus[k]).mean():.1f}, J {J[k]:.3f}')
for t in (0.1, 0.2, 0.3, 0.4):
    print(f'  tau {t:.1f}: yakalama %{100 * (r > t).mean():.1f}, zemin yanlis %{100 * (g > t).mean():.1f}')
