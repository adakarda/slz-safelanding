#!/usr/bin/env python3
"""Replay the mode's PI offline from the recorded reference and speed, and
compare it with what the recorder reconstructed (I_hesap) and with the
command the mode actually sent (v_cmd).

    tools/veri/pi_tekrar.py EP_DIR [EP_DIR ...] [--kp 0.8 --ki 0.6 --kaw 1.0]

Same law as DescentRateController::update (emergency_landing_mode.hpp):
    e = v_ref - v_meas ; u = v_ref + Kp e + I ; u_sat = clamp(u, 0, v_max)
    I += (Ki e + Kaw (u_sat - u)) dt        reset to 0 on entering VALIDATE
I_hesap is the integral the mode used at that tick, so it is compared with
the replayed integral BEFORE its update.

The replay runs on the 50 Hz grid with held values (v_ref arrives at ~10 Hz
on /eland/state); the mode runs at its own ~30-50 Hz with fresh samples.
Some difference is therefore expected and is what this reports.
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dogrula import load_csv  # noqa: E402

VALIDATE = 2


def replay(d, kp, ki, kaw, vmax, dt=0.02):
    n = len(d['t_gz'])
    u_out = np.full(n, np.nan)
    i_out = np.full(n, np.nan)
    integ = 0.0
    prev_val = False
    for k in range(n):
        val = d['durum'][k] == VALIDATE
        if not val:
            prev_val = False
            continue
        if not prev_val:
            integ = 0.0            # bumpless entry, as transition() resets it
        prev_val = True
        vr, vm = d['v_ref'][k], d['vz_ekf'][k]
        if not (np.isfinite(vr) and np.isfinite(vm)):
            continue
        e = vr - vm
        u = vr + kp * e + integ
        us = min(max(u, 0.0), vmax)
        i_out[k] = integ
        u_out[k] = us
        integ += (ki * e + kaw * (us - u)) * dt
    return u_out, i_out


def stats(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if not m.any():
        return dict(n=0)
    diff = a[m] - b[m]
    return dict(n=int(m.sum()), rms=float(np.sqrt(np.mean(diff ** 2))),
                ort=float(np.mean(diff)), en_buyuk=float(np.max(np.abs(diff))),
                r=float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() > 2 else float('nan'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('eps', nargs='+')
    p.add_argument('--kp', type=float, default=0.8)
    p.add_argument('--ki', type=float, default=0.6)
    p.add_argument('--kaw', type=float, default=1.0)
    p.add_argument('--vmax', type=float, default=1.5)
    a = p.parse_args()
    print('| bolum | n | v_cmd: tekrar - kayit RMS / ort / en buyuk (m/s) | '
          'I: tekrar - I_hesap RMS / ort / en buyuk (m/s) | I korelasyon |')
    print('|---|---|---|---|---|')
    all_u, all_i = [], []
    for ep in a.eps:
        d = load_csv(os.path.join(ep, 'duzenli.csv'))
        u, i = replay(d, a.kp, a.ki, a.kaw, a.vmax)
        su = stats(u, d['v_cmd'])
        si = stats(i, d['I_hesap'])
        m = np.isfinite(u) & np.isfinite(d['v_cmd'])
        all_u.append(u[m] - d['v_cmd'][m])
        m2 = np.isfinite(i) & np.isfinite(d['I_hesap'])
        all_i.append(i[m2] - d['I_hesap'][m2])
        if su.get('n'):
            print(f"| {os.path.basename(ep.rstrip('/'))} | {su['n']} | "
                  f"{su['rms']:.4f} / {su['ort']:+.4f} / {su['en_buyuk']:.3f} | "
                  f"{si.get('rms', float('nan')):.4f} / {si.get('ort', float('nan')):+.4f} / "
                  f"{si.get('en_buyuk', float('nan')):.3f} | {si.get('r', float('nan')):.3f} |")
    du, di = np.concatenate(all_u), np.concatenate(all_i)
    print(f'\ntoplam: v_cmd farki RMS {np.sqrt(np.mean(du ** 2)):.4f} m/s (n={len(du)}), '
          f'I farki RMS {np.sqrt(np.mean(di ** 2)):.4f} m/s (n={len(di)})')


if __name__ == '__main__':
    main()
