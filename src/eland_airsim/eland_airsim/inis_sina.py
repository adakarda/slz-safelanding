"""Phase 3 measurement: one emergency landing in AirSim, scored from AirSim's ground truth.

    ~/airsim-venv/bin/python -m eland_airsim.inis_sina [--sure 300] [--out FILE]

Start it once run_airsim.sh has taken off and selected the mode (it prints "hazir."). It follows the
vehicle at 20 Hz until it has stood still on the ground for 3 s, then records:
  - touchdown vertical speed (largest downward speed in the last 0.5 s before it stopped)
  - where it landed, relative to where the mode was selected
  - what it landed on: AirSim's segmentation under the camera (centre of the downward image, which at
    0.1 m sees the ground right under the vehicle) and the object AirSim reports it collided with
The same quantities run_sim.sh's runs are judged on (touchdown speed, landing class).
"""
import argparse
import collections
import json
import time

import numpy as np

from . import istemci, siniflar

LANDED_SPEED = 0.15      # m/s, all three axes together
LANDED_HOLD_S = 3.0


def labels_under(c, camera='asagi', frac=0.3):
    """Class histogram of the centre `frac` of the downward segmentation image."""
    import airsim
    r = c.simGetImages([airsim.ImageRequest(camera, airsim.ImageType.Segmentation, False, False)])[0]
    seg = np.frombuffer(r.image_data_uint8, np.uint8).reshape(r.height, r.width, 3)
    cls = siniflar.labels_to_classes(siniflar.decode(seg, siniflar.palette(), 'bgr'))
    h, w = cls.shape
    dh, dw = int(h * frac / 2), int(w * frac / 2)
    mid = cls[h // 2 - dh:h // 2 + dh, w // 2 - dw:w // 2 + dw]
    return {int(k): int(v) for k, v in zip(*np.unique(mid, return_counts=True))}


def ground_clearance(c, camera='asagi'):
    """Median depth (m) at the centre of the downward camera: ~0.1 on the ground."""
    import airsim
    r = c.simGetImages([airsim.ImageRequest(camera, airsim.ImageType.DepthPlanar, True, False)])[0]
    d = np.asarray(r.image_data_float, np.float32).reshape(r.height, r.width)
    h, w = d.shape
    return float(np.median(d[h // 2 - h // 10:h // 2 + h // 10, w // 2 - w // 10:w // 2 + w // 10]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sure', type=float, default=300.0, help='en uzun bekleme, duvar saniyesi')
    ap.add_argument('--host', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    c = istemci.connect(a.host, timeout_s=30)
    k = c.simGetGroundTruthKinematics()
    p0 = np.array([k.position.x_val, k.position.y_val, k.position.z_val])
    iz = collections.deque()           # (t, p, v)
    t0 = time.time()
    still_since = None
    out = {'sonuc': 'zaman_asimi'}
    while time.time() - t0 < a.sure:
        k = c.simGetGroundTruthKinematics()
        p = np.array([k.position.x_val, k.position.y_val, k.position.z_val])
        v = np.array([k.linear_velocity.x_val, k.linear_velocity.y_val, k.linear_velocity.z_val])
        t = time.time()
        iz.append((t, p, v))
        moving = np.linalg.norm(v) > LANDED_SPEED
        if moving:
            still_since = None
        elif still_since is None:
            still_since = t
        # stood still for long enough with the ground right under the camera: landed (hovering still at
        # a lower altitude while the mode searches is not)
        if still_since is not None and t - still_since >= LANDED_HOLD_S and ground_clearance(c) < 1.0:
            ts = [x for x in iz if still_since - 0.5 <= x[0] <= still_since]
            v_td = max((x[2][2] for x in ts), default=0.0)        # NED: +z is down
            col = c.simGetCollisionInfo()
            under = labels_under(c)
            known = {k_: n for k_, n in under.items() if k_ != siniflar.UNKNOWN}
            out = {'sonuc': 'indi', 'sure_s': round(still_since - t0, 1),
                   'temas_hizi_mps': round(float(v_td), 2),
                   'inis_ned': [round(float(x), 2) for x in p],
                   'yatay_uzaklik_m': round(float(np.linalg.norm(p[:2] - p0[:2])), 2),
                   'alcalma_m': round(float(p[2] - p0[2]), 2),
                   'inis_sinifi': max(known, key=known.get) if known else siniflar.UNKNOWN,
                   'alt_siniflar': under,
                   'carpisma_nesnesi': col.object_name if col.has_collided else ''}
            break
        time.sleep(0.05)
    if out['sonuc'] != 'indi':
        out['son_ned'] = [round(float(x), 2) for x in iz[-1][1]] if iz else None
    print(f'[inis] {json.dumps(out, ensure_ascii=False)}', flush=True)
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
