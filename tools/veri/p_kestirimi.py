#!/usr/bin/env python3
"""The surface-height estimate (p_kestirici) on recorded episodes, offline.

    PYTHONPATH=/usr/lib/python3/dist-packages python3 tools/veri/p_kestirimi.py \
        [--grafik] [--kok ~/eland_veri] [--dunya veri_w5 ...] [EP_DIR ...]

Same arithmetic as the live node (src/eland_mapping/eland_mapping/p_hesap.py),
on the frames the node would have used: from VALIDATE to the true touchdown,
region in view, rho in (0.003, 0.98), tilt under 5 deg. h_ekf is taken at the
mask's capture stamp from duzenli.csv, so no latency correction is needed.

What it is compared with, per episode:
- P_dogru: median of h_ekf - h_kamera_gercek over the same frames. That is
  the P the line should find -- the surface height in the EKF frame, camera
  mounting and EKF error included (h_ekf - P is the camera's distance).
- A_dogru: the target region's real area, from rho_hesap (world yaml).
- area_m2 from the map (karar_olaylari.csv) over the same window, to show
  how far off the map's own area is over a raised target.

Prints one row per episode and a summary; --grafik writes p_kestirimi.png
into each episode folder. New file; reads only.
"""
import argparse
import glob
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'src', 'eland_mapping'))
from eland_mapping import p_hesap  # noqa: E402

RHO_ALT, RHO_UST, EGIKLIK = 0.003, 0.98, 5.0


def oku(path):
    import csv
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    out = {}
    for k in rows[0]:
        try:
            out[k] = np.array([float(r[k]) if r[k] not in ('', None) else np.nan
                               for r in rows])
        except ValueError:
            out[k] = np.array([r[k] for r in rows])
    return out


def bolum(ep):
    oz = json.load(open(os.path.join(ep, 'ep_ozet.json')))
    t0, t1 = oz.get('t_validate'), oz.get('t_temas_gercek')
    if t0 is None or t1 is None or not all(map(math.isfinite, (t0, t1))):
        return None
    m = oku(os.path.join(ep, 'maske_olaylari.csv'))
    d = oku(os.path.join(ep, 'duzenli.csv'))
    if not m or not d:
        return None
    t = m['t_yakalama']
    h = np.interp(t, d['t_gz'], d['h_ekf'])
    roll = np.interp(t, d['t_gz'], d['roll'])
    pitch = np.interp(t, d['t_gz'], d['pitch'])
    egik = np.degrees(np.arccos(np.clip(np.cos(roll) * np.cos(pitch), -1, 1)))
    rho = m['rho']
    sec = ((t >= t0) & (t <= t1) & (m['view_bounded'] == 1)
           & (rho > RHO_ALT) & (rho < RHO_UST) & (egik < EGIKLIK))
    r = dict(ep=os.path.basename(ep), n=int(sec.sum()))
    if r['n'] < 3:
        return r
    fit = p_hesap.kestir(h[sec], rho[sec])
    r.update(fit or {})
    r['pencere'] = float(np.ptp(h[sec]))
    r['p_dogru'] = float(np.nanmedian(h[sec] - m['h_kamera_gercek'][sec]))
    a = m['rho_hesap'][sec] * p_hesap.AYAK_IZI * m['h_kamera_gercek'][sec] ** 2
    r['a_dogru'] = float(np.nanmedian(a)) if np.isfinite(a).any() else float('nan')
    k = oku(os.path.join(ep, 'karar_olaylari.csv'))
    if k:
        w = (k['t_alma'] >= t[sec].min()) & (k['t_alma'] <= t[sec].max()) & (k['gecerli'] == 1)
        r['a_harita'] = float(np.nanmedian(k['area_m2'][w])) if w.any() else float('nan')
    r['_h'], r['_rho'], r['_t'] = h[sec], rho[sec], t[sec]
    r['_d'] = (d, h, t, m)
    return r


def grafik(ep, r):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    d, h_all, t_all, m = r['_d']
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    y = 1 / np.sqrt(r['_rho'])
    ax[0].plot(r['_h'], y, '.', ms=4, label='kareler')
    if math.isfinite(r.get('p', float('nan'))):
        hh = np.linspace(r['p'], r['_h'].max(), 50)
        ax[0].plot(hh, r['egim'] * (hh - r['p']), 'k-', lw=1,
                   label=f"dogru: P {r['p']:+.2f} m, A {r['alan']:.0f} m2")
        ax[0].plot([r['p']], [0], 'o', mfc='none', mec='k', ms=9)
    ax[0].plot([r['p_dogru']], [0], 'g^', ms=8, label=f"dogru P {r['p_dogru']:+.2f} m")
    ax[0].set_xlabel('h_ekf [m]')
    ax[0].set_ylabel('1/sqrt(rho)')
    ax[0].set_xlim(left=min(0, r['p_dogru'] - 1))
    ax[0].set_ylim(bottom=0)
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=.3)
    tt = d['t_gz']
    ax[1].plot(tt, d['h_ekf'], label='h_ekf (kalkisa gore)')
    ax[1].plot(tt, d['h_gercek_hedef'], label='gercek, hedefe gore')
    if math.isfinite(r.get('p', float('nan'))):
        ax[1].plot(tt, d['h_ekf'] - r['p'], '--', label='h_ekf - P (kestirim)')
    ax[1].axvspan(r['_t'].min(), r['_t'].max(), color='orange', alpha=.15,
                  label='olcum penceresi')
    ax[1].set_xlabel('t [s]')
    ax[1].set_ylabel('yukseklik [m]')
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=.3)
    fig.suptitle(r['ep'])
    fig.tight_layout()
    fig.savefig(os.path.join(ep, 'p_kestirimi.png'), dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('ep', nargs='*')
    ap.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    ap.add_argument('--dunya', nargs='*', default=[])
    ap.add_argument('--grafik', action='store_true')
    a = ap.parse_args()
    eps = list(a.ep)
    for dn in a.dunya:
        eps += sorted(glob.glob(os.path.join(a.kok, '[!_]*', dn, '*')))
    eps = [e for e in eps if os.path.exists(os.path.join(e, 'ep_ozet.json'))]
    print(f'{"bolum":34s} {"kare":>4s} {"pencere":>7s} {"P_kest":>7s} {"+-":>5s} '
          f'{"P_dogru":>7s} {"hata":>6s} {"A_kest":>6s} {"A_dogru":>7s} {"A_harita":>8s}')
    hatalar = []
    for ep in eps:
        r = bolum(ep)
        if r is None:
            continue
        if r['n'] < 3 or not math.isfinite(r.get('p', float('nan'))):
            print(f"{r['ep']:34s} {r['n']:4d}   (dogru yok)")
            continue
        e = r['p'] - r['p_dogru']
        hatalar.append(e)
        print(f"{r['ep']:34s} {r['n']:4d} {r['pencere']:7.1f} {r['p']:+7.2f} "
              f"{r['p_sigma']:5.2f} {r['p_dogru']:+7.2f} {e:+6.2f} {r['alan']:6.0f} "
              f"{r['a_dogru']:7.0f} {r.get('a_harita', float('nan')):8.0f}")
        if a.grafik:
            grafik(ep, r)
    if hatalar:
        h = np.abs(np.array(hatalar))
        print(f'\n{len(h)} bolum: |P hatasi| ortanca {np.median(h):.2f} m, '
              f'p95 {np.percentile(h, 95):.2f} m, en buyuk {h.max():.2f} m')


if __name__ == '__main__':
    main()
