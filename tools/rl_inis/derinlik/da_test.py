"""Depth Anything V2 Small on nadir MESSI photos: does its depth separate raised things from the ground?

Relative (affine-invariant) inverse depth: larger = closer to the camera = higher above ground.
Per photo, AUC of the prediction for
  building / wall / awning (MESSI 2, 3, 8)  vs  ground (asphalt 11, sidewalk 14, grass 9, bare soil 7)
  tree (12)                                 vs  grass (9)
AUC 0.5 = no information, 1.0 = perfect separation. Also saves a few side-by-side images.

    python da_test.py <messi_rl dir> <out dir> [n_photos]
"""
import csv
import os
import sys
import time

import cv2
import numpy as np
import torch
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

MODEL = 'depth-anything/Depth-Anything-V2-Small-hf'
GROUND = [11, 14, 9, 7]
RAISED = [2, 3, 8]


def auc(pos, neg, n=20000, rng=np.random.default_rng(0)):
    if len(pos) < 50 or len(neg) < 50:
        return float('nan')
    p = rng.choice(pos, min(n, len(pos)))
    q = rng.choice(neg, min(n, len(neg)))
    allv = np.concatenate([p, q])
    ranks = allv.argsort().argsort() + 1
    return float((ranks[:len(p)].sum() - len(p) * (len(p) + 1) / 2) / (len(p) * len(q)))


def main(root, out, n):
    os.makedirs(out, exist_ok=True)
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    proc = AutoImageProcessor.from_pretrained(MODEL)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL).to(dev).eval()
    man = [m for m in csv.DictReader(open(f'{root}/manifest.csv')) if os.path.exists(f"{root}/{m['img']}")]
    sel = man[:: max(1, len(man) // n)][:n]
    rows = []
    for i, m in enumerate(sel):
        bgr = cv2.imread(f"{root}/{m['img']}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        small = cv2.resize(rgb, (1036, 690), interpolation=cv2.INTER_AREA)
        t0 = time.time()
        with torch.no_grad():
            inp = proc(images=small, return_tensors='pt').to(dev)
            pred = model(**inp).predicted_depth[0].float().cpu().numpy()
        ms = (time.time() - t0) * 1000
        raw = cv2.imread(f"{root}/{m['mask_raw16']}", cv2.IMREAD_UNCHANGED)
        raw = cv2.resize(raw, (pred.shape[1], pred.shape[0]), interpolation=cv2.INTER_NEAREST)
        a_b = auc(pred[np.isin(raw, RAISED)], pred[np.isin(raw, GROUND)])
        a_t = auc(pred[raw == 12], pred[raw == 9])
        rows.append((m['ad'], m['tur'], float(m['rel_alt_m']), a_b, a_t, ms))
        print(f"{m['ad']:16s} {m['tur']:7s} {float(m['rel_alt_m']):5.1f} m  AUC bina/zemin {a_b:.3f}  agac/cim {a_t:.3f}  {ms:.0f} ms", flush=True)
        if i < 6:
            d = (pred - np.percentile(pred, 2)) / max(np.percentile(pred, 98) - np.percentile(pred, 2), 1e-6)
            d = cv2.applyColorMap((np.clip(d, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
            ph = cv2.resize(bgr, (d.shape[1], d.shape[0]), interpolation=cv2.INTER_AREA)
            cv2.imwrite(f"{out}/da_{m['ad']}.jpg", np.concatenate([ph, d], 1), [cv2.IMWRITE_JPEG_QUALITY, 80])
    r = np.array([x[3:] for x in rows], float)
    print(f'\n{len(rows)} foto: AUC bina/zemin medyan {np.nanmedian(r[:, 0]):.3f} (min {np.nanmin(r[:, 0]):.3f}), '
          f'agac/cim medyan {np.nanmedian(r[:, 1]):.3f} (min {np.nanmin(r[:, 1]):.3f}), sure medyan {np.median(r[:, 2]):.0f} ms')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 24)
