"""Explainer images: what the camera sees and what the policy gets, at one pose."""
import base64
import json
import sys

import cv2
import numpy as np

from eland_common import classes
from eland_rl.camera import Camera, rotation
from eland_rl.scene import Scene

RENK = np.array([classes.CLASS_COLORS[i] for i in range(8)], np.uint8)
sc = Scene.from_messi('/home/arda/v3_test/foto/fotoo/DJI_0266.JPG', '/home/arda/v3_test/maske/fotomask/DJI_0266.png',
                      load_photo=True)
out = {}
for ad, (x, y, h, egim) in {'p25': (8.0, -6.0, 25.0, 0.0), 'p25_egik': (8.0, -6.0, 25.0, 1.5)}.items():
    R = rotation((egim, 0.0, 9.81), 0.0)      # egim: x ivmesi m/s2 -> burun asagi
    c = np.array([x, y, h])
    rgb = Camera.rgb_image(sc, c, R, 320, 240) if ad == 'p25' else None
    lab = Camera.label_image(sc, c, R, 320, 240)
    sem, depth = Camera().semantic_depth(sc, c, R)
    imgs = {'etiket': RENK[lab], 'girdi_sem': cv2.resize(RENK[sem], (256, 256), interpolation=cv2.INTER_NEAREST),
            'girdi_derinlik': cv2.resize(np.clip(depth / 40 * 255, 0, 255).astype(np.uint8), (256, 256),
                                         interpolation=cv2.INTER_NEAREST)}
    if rgb is not None:
        imgs['rgb'] = rgb
    for k, im in imgs.items():
        if im.ndim == 3:
            im = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)
        ok, b = cv2.imencode('.jpg' if k == 'rgb' else '.png', im, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out[f'{ad}_{k}'] = ('data:image/jpeg;base64,' if k == 'rgb' else 'data:image/png;base64,') + base64.b64encode(b).decode()
    pay = np.bincount(sem.ravel(), minlength=8) / sem.size
    out[f'{ad}_pay'] = [round(float(v), 3) for v in pay]
    out[f'{ad}_derinlik'] = [round(float(depth.min()), 2), round(float(depth.max()), 2)]
json.dump(out, open(sys.argv[1], 'w'))
print({k: (len(v) if isinstance(v, str) else v) for k, v in out.items()})
