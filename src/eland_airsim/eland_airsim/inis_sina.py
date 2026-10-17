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
LANDED_SPAN_M = 0.10     # or: moved less than this, on every axis, over LANDED_HOLD_S


def airsim_alive():
    """Is an AirSim world process still running on Windows (tasklist.exe through WSL interop)?"""
    import subprocess
    try:
        out = subprocess.run(['tasklist.exe'], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return True                      # cannot tell; do not claim a crash
    return any(w in out for w in ('AirSimNH', 'CityEnviron'))


class Reconnecting:
    """An AirSim client that reconnects when AirSim resets the connection.

    AirSim reset this script's RPC connection in the middle of two Faz 3 runs (ConnectionResetError
    while the bridge's own two connections kept working), which lost the measurement of a landing that
    had gone fine. Every call is retried on a fresh connection, up to `tries` times.
    """

    def __init__(self, host, tries=8):
        self.host, self.tries = host, tries
        self.c = istemci.connect(host, timeout_s=30)

    def __call__(self, fn):
        for i in range(self.tries):
            try:
                return fn(self.c)
            except (ConnectionError, OSError, EOFError) as e:
                if i == self.tries - 1:
                    raise
                print(f'[inis] AirSim baglantisi koptu ({type(e).__name__}), yeniden baglaniliyor; '
                      f'AirSim sureci {"var" if airsim_alive() else "YOK"}', flush=True)
                time.sleep(min(2.0 * (i + 1), 10.0))
                try:
                    self.c = istemci.connect(self.host, timeout_s=10)
                except (ConnectionError, OSError, EOFError):
                    pass                        # the next round tries again on the old (dead) client


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


def follow(rpc, a):
    """Track the vehicle until it has landed (or the time is up); the result dict."""
    k = rpc(lambda c: c.simGetGroundTruthKinematics())
    p0 = np.array([k.position.x_val, k.position.y_val, k.position.z_val])
    iz = collections.deque()           # (t, p, v)
    t0 = time.time()
    still_since = None
    last_depth = 0.0
    out = {'sonuc': 'zaman_asimi'}
    while time.time() - t0 < a.sure:
        k = rpc(lambda c: c.simGetGroundTruthKinematics())
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
        # The depth image is asked for at most once a second: while the classic mode hovers still at its
        # search altitude this would otherwise run at 20 Hz next to the bridge's image stream (suspected
        # cause of AirSim dropping all RPC connections in the second Faz 3 batch).
        # "Still" is judged on displacement as well as speed: one Faz 3 landing sat on the ground with its
        # ground-truth speed jittering above 0.15 m/s and was never counted (timed out).
        recent = [x[1] for x in iz if x[0] >= t - LANDED_HOLD_S]
        settled = (t - t0 >= LANDED_HOLD_S and len(recent) > 5
                   and float(np.ptp(np.array(recent), axis=0).max()) < LANDED_SPAN_M)
        held = settled or (still_since is not None and t - still_since >= LANDED_HOLD_S)
        if held and t - last_depth >= 1.0:
            last_depth = t
            on_ground = rpc(ground_clearance) < 1.0
        else:
            on_ground = False
        if held and on_ground:
            # touchdown: the first sample within 5 cm of the resting height
            t_td = next(x[0] for x in iz if abs(x[1][2] - p[2]) < 0.05)
            ts = [x for x in iz if t_td - 0.5 <= x[0] <= t_td]
            v_td = max((x[2][2] for x in ts), default=0.0)        # NED: +z is down
            col = rpc(lambda c: c.simGetCollisionInfo())
            under = rpc(labels_under)
            known = {k_: n for k_, n in under.items() if k_ != siniflar.UNKNOWN}
            out = {'sonuc': 'indi', 'sure_s': round(t_td - t0, 1),
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
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sure', type=float, default=300.0, help='en uzun bekleme, duvar saniyesi')
    ap.add_argument('--host', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    try:
        rpc = Reconnecting(a.host)
    except (ConnectionError, OSError, EOFError) as e:
        out = {'sonuc': 'airsim_yok', 'hata': type(e).__name__, 'airsim_sureci': airsim_alive()}
        print(f'[inis] {json.dumps(out, ensure_ascii=False)}', flush=True)
        if a.out:
            json.dump(out, open(a.out, 'w'), indent=1)
        return
    try:
        out = follow(rpc, a)
    except (ConnectionError, OSError, EOFError) as e:
        out = {'sonuc': 'kopma', 'hata': type(e).__name__, 'airsim_sureci': airsim_alive()}
    print(f'[inis] {json.dumps(out, ensure_ascii=False)}', flush=True)
    if a.out:
        json.dump(out, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
