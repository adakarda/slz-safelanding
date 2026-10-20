"""Depth Anything V2 Small relative elevation for every MESSI photo (amendment 7).

Output: <out>/elev/<id>.png, 8-bit, same size as the factor-4 scene masks. Per photo the
relative inverse depth is mapped to 0..1 between its 5th and 99.5th percentiles, so 0 is the
ground level and 1 the highest roofs -- a scale-free 'how raised is this' map that the vehicle
could compute from a single frame too.
"""
import csv
import os
import sys

import cv2
import numpy as np
import torch
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

MODEL = 'depth-anything/Depth-Anything-V2-Small-hf'
root, out = sys.argv[1], sys.argv[2]
os.makedirs(f'{out}/elev', exist_ok=True)
dev = 'cuda' if torch.cuda.is_available() else 'cpu'
proc = AutoImageProcessor.from_pretrained(MODEL)
model = AutoModelForDepthEstimation.from_pretrained(MODEL).to(dev).eval()
man = [m for m in csv.DictReader(open(f'{root}/manifest.csv')) if os.path.exists(f"{root}/{m['img']}")]
for m in man:
    name = m['id'].replace('/', '__')
    bgr = cv2.imread(f"{root}/{m['img']}")
    rgb = cv2.cvtColor(cv2.resize(bgr, (1036, 690), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    with torch.no_grad():
        pred = model(**proc(images=rgb, return_tensors='pt').to(dev)).predicted_depth[0].float().cpu().numpy()
    lo, hi = np.percentile(pred, 5), np.percentile(pred, 99.5)
    e = np.clip((pred - lo) / max(hi - lo, 1e-6), 0, 1)
    w, h = int(m['w']) // 4, int(m['h']) // 4
    cv2.imwrite(f'{out}/elev/{name}.png', (cv2.resize(e, (w, h), interpolation=cv2.INTER_LINEAR) * 255).astype(np.uint8))
print(len(man), 'yukseklik haritasi ->', f'{out}/elev')
