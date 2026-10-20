"""Tampon mesafesine gore guvenli alan payi (hafif: torch yok). Duz alcalmanin beklenen basarisini verir."""
import sys

import numpy as np

from eland_rl.scenes import load_list

sc = load_list(sys.argv[1], dist_cell_m=0.25)
for m in (0.0, 1.0, 2.0, 3.0):
    f = []
    for s in sc:
        safe, _, _ = s._sora_grid(m)
        gh, gw = safe.shape
        # baslangiclar fotonun ortasinda yogun: kenardan %15 iceriyi al
        f.append(safe[int(.15 * gh):int(.85 * gh), int(.15 * gw):int(.85 * gw)].mean())
    print(f'tampon {m:.0f} m: guvenli alan payi (ortadaki %70x%70) ort {np.mean(f) * 100:5.1f} %  min {np.min(f) * 100:4.1f}  max {np.max(f) * 100:4.1f}')
