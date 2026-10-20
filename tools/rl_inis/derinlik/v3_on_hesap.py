"""v3 class predictions for every MESSI photo, as downsampled scene masks like the GT ones (amendment 7).

Runs in the v3 venv. Output: <out>/pred/<id>.png (taxonomy 0..6, factor-4 hazard-priority shrink)
and a per-photo agreement with the GT SORA-7 mask (pixel accuracy, mIoU over present classes).
"""
import csv
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, '/home/arda/v3_test/model')
sys.path.insert(0, '/home/arda/v3_test')
import v3_model as M  # noqa: E402


RANK = np.array([0, 1, 3, 4, 5, 6, 7, 2], np.uint8)
CLS = np.argsort(RANK).astype(np.uint8)


def shrink(mask, f=4):
    h, w = (mask.shape[0] // f) * f, (mask.shape[1] // f) * f
    return CLS[RANK[mask[:h, :w]].reshape(h // f, f, w // f, f).max(axis=(1, 3))]


root, out = sys.argv[1], sys.argv[2]
os.makedirs(f'{out}/pred', exist_ok=True)
model = M.yukle('/home/arda/v3_test/model/best_v3.pth')
man = [m for m in csv.DictReader(open(f'{root}/manifest.csv')) if os.path.exists(f"{root}/{m['img']}")]
rows = []
for m in man:
    name = m['id'].replace('/', '__')
    dst = f'{out}/pred/{name}.png'
    rgb = cv2.cvtColor(cv2.imread(f"{root}/{m['img']}"), cv2.COLOR_BGR2RGB)
    t0 = time.time()
    # half resolution (~4.7 cm/px, inside v3's 0.3-7 cm/px training range): our scene masks are
    # 7.5-11 cm/px anyway, and full resolution starved the GPU next to training (amendment 7)
    half = cv2.resize(rgb, (rgb.shape[1] // 2, rgb.shape[0] // 2), interpolation=cv2.INTER_AREA)
    pred = cv2.resize(M.segmentle(model, half, gsd_cm=None), (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)
    ms = (time.time() - t0) * 1000
    gt = cv2.imread(f"{root}/{m['mask_sora7']}", cv2.IMREAD_UNCHANGED)
    ok = gt < 7
    acc = float((pred[ok] == gt[ok]).mean())
    ious = []
    for c in range(7):
        p, g = (pred == c) & ok, (gt == c) & ok
        if g.sum() > 1000:
            ious.append((p & g).sum() / max((p | g).sum(), 1))
    cv2.imwrite(dst, shrink(np.where(ok | (pred < 7), pred, 7).astype(np.uint8)))
    rows.append((name, m['seq'], acc, float(np.mean(ious)), ms))
    print(f"{name[-40:]:40s} dogruluk {acc:.3f} mIoU {np.mean(ious):.3f} {ms:.0f} ms", flush=True)
r = np.array([x[2:] for x in rows])
print(f'\n{len(rows)} foto: piksel dogrulugu medyan {np.median(r[:, 0]):.3f}, mIoU medyan {np.median(r[:, 1]):.3f}, '
      f'sure medyan {np.median(r[:, 2]):.0f} ms')
with open(f'{out}/pred_ozet.csv', 'w', newline='') as fh:
    csv.writer(fh).writerows([('ad', 'seq', 'dogruluk', 'miou', 'ms')] + rows)
