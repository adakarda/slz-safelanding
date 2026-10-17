"""Phase 2 check: PX4 (WSL) <-> AirSim. Take off, hover, land; several times.

    ~/airsim-venv/bin/python -m eland_airsim.px4_sina [--tekrar 3] [--irtifa 10] [--aski 60] [--out FILE]

Run while `run_airsim.sh --yalniz-px4` is up. PX4 is commanded with px4-commander, as run_sim.sh does;
everything is measured from AirSim's ground-truth kinematics and its simulation clock.
Gate (pre-registered in the roadmap): every trial takes off, hovers and lands; horizontal drift while
hovering < 0.5 m; real-time factor >= 0.8.
"""
import argparse
import json
import os
import subprocess
import time

import numpy as np

from . import istemci

PX4_BIN = os.path.expanduser('~/PX4-Autopilot/build/px4_sitl_default/bin')


def px4(*args, timeout=15):
    try:
        r = subprocess.run([os.path.join(PX4_BIN, args[0]), *args[1:]], capture_output=True, text=True,
                           timeout=timeout)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 'zaman asimi'


def armed():
    return 'armed: True' in px4('px4-listener', 'actuator_armed')


def kinematics(c):
    k = c.simGetGroundTruthKinematics()
    p, v = k.position, k.linear_velocity
    return np.array([p.x_val, p.y_val, p.z_val]), np.array([v.x_val, v.y_val, v.z_val])


def sim_s(c):
    return c.getMultirotorState().timestamp * 1e-9


def trial(c, a, log):
    p0, _ = kinematics(c)
    z0 = p0[2]                                                     # NED: altitude = z0 - z
    px4('px4-param', 'set', 'MIS_TAKEOFF_ALT', str(a.irtifa))
    t = time.time()
    while not armed():
        if time.time() - t > 60:
            return {'sonuc': 'kurulamadi', 'px4': px4('px4-commander', 'check')[-600:]}
        px4('px4-commander', 'arm', '-f')
        time.sleep(2)
    px4('px4-commander', 'takeoff')
    t = time.time()
    while True:
        p, _ = kinematics(c)
        if z0 - p[2] > 0.9 * a.irtifa:
            break
        if time.time() - t > 90:
            return {'sonuc': 'kalkamadi', 'irtifa_m': round(float(z0 - p[2]), 2)}
        time.sleep(0.2)
    t_takeoff = time.time() - t
    time.sleep(5.0)                                                # let the climb settle
    ps, s0, w0 = [], sim_s(c), time.time()
    while sim_s(c) - s0 < a.aski and time.time() - w0 < 4 * a.aski:
        ps.append(kinematics(c)[0])
        time.sleep(0.1)
    s1, w1 = sim_s(c), time.time()
    ps = np.array(ps)
    drift = float(np.max(np.linalg.norm(ps[:, :2] - ps[0, :2], axis=1)))
    px4('px4-commander', 'land')
    t = time.time()
    while True:
        p, v = kinematics(c)
        if z0 - p[2] < 0.3 and np.linalg.norm(v) < 0.2 and not armed():
            break
        if time.time() - t > 120:
            return {'sonuc': 'inemedi', 'irtifa_m': round(float(z0 - p[2]), 2), 'kurulu': armed()}
        time.sleep(0.5)
    out = {'sonuc': 'tamam', 'kalkis_s': round(t_takeoff, 1), 'aski_sim_s': round(s1 - s0, 1),
           'aski_duvar_s': round(w1 - w0, 1), 'gzo': round((s1 - s0) / (w1 - w0), 3),
           'yatay_sapma_m': round(drift, 3), 'dikey_std_m': round(float(np.std(ps[:, 2])), 3),
           'inis_s': round(time.time() - t, 1), 'inis_yatay_m': round(float(np.linalg.norm(p[:2] - ps[0, :2])), 2)}
    log(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tekrar', type=int, default=3)
    ap.add_argument('--irtifa', type=float, default=10.0)
    ap.add_argument('--aski', type=float, default=60.0, help='askida kalma, simulasyon saniyesi')
    ap.add_argument('--host', default='')
    ap.add_argument('--out', default='')
    a = ap.parse_args()
    c = istemci.connect(a.host, timeout_s=30)
    sonuc = []
    for i in range(a.tekrar):
        r = trial(c, a, lambda o: print(f'[sina] deneme {i + 1}: {o}', flush=True))
        if r['sonuc'] != 'tamam':
            print(f'[sina] deneme {i + 1}: {r}', flush=True)
        sonuc.append(r)
        time.sleep(5.0)
    tamam = [r for r in sonuc if r['sonuc'] == 'tamam']
    gecti = (len(tamam) == a.tekrar and max(r['yatay_sapma_m'] for r in tamam) < 0.5
             and min(r['gzo'] for r in tamam) >= 0.8)
    ozet = {'deneme': sonuc, 'tamam': len(tamam), 'kapi': 'GECTI' if gecti else 'KALDI'}
    print(f'[sina] KAPI: {len(tamam)}/{a.tekrar} tamam; '
          + (f"en buyuk sapma {max(r['yatay_sapma_m'] for r in tamam):.3f} m, "
             f"en dusuk gzo {min(r['gzo'] for r in tamam):.3f}; " if tamam else '') + ozet['kapi'], flush=True)
    if a.out:
        json.dump(ozet, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
