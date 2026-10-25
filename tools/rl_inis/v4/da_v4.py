"""v4 RL sahneleri icin Depth Anything V2 Small goreli yukseklik haritalari (Duzeltme 7 / 27 ile ayni yol: tam
goruntu 1036 px genislige, %5-%99.5 yuzdelik olcekleme, maske boyuna).

    $RL_PY da_v4.py          # biten haritalar atlanir
"""
import csv
import os

import cv2
import numpy as np
import torch
from transformers import AutoImageProcessor, AutoModelForDepthEstimation

V = os.path.expanduser('~/eland_veri/v4_zip/veri_v4')
O = os.path.expanduser('~/eland_veri/rl/v4')
MODEL = 'depth-anything/Depth-Anything-V2-Small-hf'


def main():
    dev = 'cuda' if torch.cuda.is_available() else 'cpu'
    proc = AutoImageProcessor.from_pretrained(MODEL, local_files_only=True)
    model = AutoModelForDepthEstimation.from_pretrained(MODEL, local_files_only=True).to(dev).eval()
    yol = {m['id'].replace('/', '__'): f"{V}/{m['goruntu']}" for m in csv.DictReader(open(f'{V}/manifest.csv'))}
    satir = [l.split() for b in ('train', 'val', 'test') for l in open(f'{O}/{b}.txt')]
    n = 0
    for s in satir:
        mp, ep = s[0], s[3][5:]
        if os.path.exists(ep):
            continue
        ad = os.path.basename(mp)[:-4]
        p = yol.get(ad)
        if p is None:
            print('goruntu yok:', ad)
            continue
        bgr = cv2.imread(p)
        h0, w0 = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (1036, round(1036 * h0 / w0)), interpolation=cv2.INTER_AREA),
                           cv2.COLOR_BGR2RGB)
        with torch.no_grad():
            pred = model(**proc(images=rgb, return_tensors='pt').to(dev)).predicted_depth[0].float().cpu().numpy()
        lo, hi = np.percentile(pred, 5), np.percentile(pred, 99.5)
        e = np.clip((pred - lo) / max(hi - lo, 1e-6), 0, 1)
        mh, mw = cv2.imread(mp, cv2.IMREAD_UNCHANGED).shape[:2]
        os.makedirs(os.path.dirname(ep), exist_ok=True)
        cv2.imwrite(ep, (cv2.resize(e, (mw, mh), interpolation=cv2.INTER_LINEAR) * 255).astype(np.uint8))
        n += 1
        if n % 200 == 0:
            print(n, 'harita', flush=True)
    print(n, 'yeni harita; toplam', len(satir))


if __name__ == '__main__':
    main()
