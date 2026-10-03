#!/usr/bin/env python3
"""Plant identification from K5 square-wave episodes (open loop).

    tools/veri/tesis_analizi.py KOK_DIZIN [--cikti DIR]

KOK_DIZIN holds k5_A*/.../<ep>/duzenli.csv folders. For every command edge
(the identification branch switches v_cmd every half period) the response of
the vertical speed is measured:

  K       steady-state gain: change in mean speed over the last 1 s of the
          half period / change in command. Dimensionless.
  theta   dead time: edge -> speed has moved 10 % of its final change.
  t90     edge -> 90 %.
  egim    largest |dv/dt| between 10 % and 90 %, m/s^2 -- the slope limit.

Only edges with a full half period on both sides, the commanded value
unchanged by the 8-25 m guard rails, and the aircraft above 8 m (ground truth)
are used. Both the EKF estimate and the Gazebo-derived speed are evaluated.
"""
import argparse
import glob
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dogrula import load_csv  # noqa: E402

SERIES = ('#2a78d6', '#eb6834', '#1baf7a')
SURFACE, INK, INK2, MUTED, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#898781', '#e1e0d9'


def edges(t, u, min_gap=3.5):
    """Indices where the command steps, with a quiet half period around."""
    du = np.diff(u)
    idx = np.nonzero(np.abs(du) > 0.1)[0] + 1
    keep = []
    for k, i in enumerate(idx):
        prev_t = t[idx[k - 1]] if k > 0 else -np.inf
        next_t = t[idx[k + 1]] if k + 1 < len(idx) else np.inf
        if t[i] - prev_t >= min_gap and next_t - t[i] >= min_gap:
            keep.append((i, next_t))
    return keep


def step_metrics(t, u, v, i, t_next):
    t_e = t[i]
    before = (t >= t_e - 1.0) & (t < t_e)
    after_ss = (t >= min(t_next, t_e + 4.0) - 1.0) & (t < min(t_next, t_e + 4.0))
    win = (t >= t_e) & (t < min(t_next, t_e + 4.0))
    if before.sum() < 10 or after_ss.sum() < 10 or win.sum() < 20:
        return None
    u0, u1 = np.nanmean(u[before]), np.nanmean(u[after_ss])
    v0, v1 = np.nanmean(v[before]), np.nanmean(v[after_ss])
    du, dv = u1 - u0, v1 - v0
    if abs(du) < 0.1 or abs(dv) < 0.05:
        return None
    tw, vw = t[win] - t_e, v[win]
    frac = (vw - v0) / dv
    def first(level):
        hit = np.nonzero(frac >= level)[0]
        return float(tw[hit[0]]) if len(hit) else float('nan')
    th, t90 = first(0.1), first(0.9)
    slope = np.gradient(vw, tw)
    rising = (frac >= 0.1) & (frac <= 0.9)
    egim = float(np.nanmax(np.abs(slope[rising]))) if rising.any() else float('nan')
    return dict(du=du, K=dv / du, theta=th, t90=t90, egim=egim, yon='asagi' if du > 0 else 'yukari',
                tw=tw, frac=frac)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('kok')
    p.add_argument('--cikti', default=None)
    a = p.parse_args()
    out = a.cikti or os.path.join(a.kok, 'dogrulama', 'k5')
    os.makedirs(out, exist_ok=True)
    rows = {}
    curves = {}
    for path in sorted(glob.glob(os.path.join(a.kok, 'k5_A*', '*', '*', 'duzenli.csv'))):
        amp = path.split(os.sep)[-4].replace('k5_A', '')
        d = load_csv(path)
        ok = (d['durum'] == 2) & np.isfinite(d['v_cmd']) & (d['h_gercek_zemin'] > 8.0)
        t, u = d['t_gz'][ok], d['v_cmd'][ok]
        for src in ('vz_ekf', 'vz_gercek_hesap'):
            v = d[src][ok]
            for i, t_next in edges(t, u):
                m = step_metrics(t, u, v, i, t_next)
                if m is None:
                    continue
                rows.setdefault((amp, src), []).append(m)
                if src == 'vz_gercek_hesap':
                    curves.setdefault(amp, []).append((m['tw'], m['frac']))

    lines = ['| genlik | hiz kaynagi | n basamak | K ortanca [min, max] | olu zaman θ ortanca | t90 ortanca | egim siniri ortanca (m/s²) | yukari / asagi egim |',
             '|---|---|---|---|---|---|---|---|']
    for (amp, src), ms in sorted(rows.items(), key=lambda kv: (float(kv[0][0]), kv[0][1])):
        K = np.array([m['K'] for m in ms])
        th = np.array([m['theta'] for m in ms])
        t9 = np.array([m['t90'] for m in ms])
        eg = np.array([m['egim'] for m in ms])
        up = np.array([m['egim'] for m in ms if m['yon'] == 'yukari'])
        dn = np.array([m['egim'] for m in ms if m['yon'] == 'asagi'])
        lines.append(f'| {amp} | {src} | {len(ms)} | {np.nanmedian(K):.3f} [{np.nanmin(K):.3f}, {np.nanmax(K):.3f}] | '
                     f'{np.nanmedian(th):.3f} s | {np.nanmedian(t9):.2f} s | {np.nanmedian(eg):.2f} | '
                     f'{np.nanmedian(up) if len(up) else float("nan"):.2f} / {np.nanmedian(dn) if len(dn) else float("nan"):.2f} |')
    text = '\n'.join(lines)
    with open(os.path.join(out, 'tesis_tablosu.md'), 'w') as f:
        f.write(text + '\n')
    print(text)

    if curves:
        amps = sorted(curves, key=float)
        fig, axes = plt.subplots(1, len(amps), figsize=(3.2 * len(amps), 3.4), sharey=True,
                                 facecolor=SURFACE)
        axes = np.atleast_1d(axes)
        for ax, amp in zip(axes, amps):
            ax.set_facecolor(SURFACE)
            for spine in ('top', 'right'):
                ax.spines[spine].set_visible(False)
            ax.grid(True, axis='y', color=GRID, linewidth=0.6)
            grid = np.linspace(0, 3.5, 176)
            stack = []
            for tw, fr in curves[amp]:
                g = np.interp(grid, tw, fr, left=np.nan, right=np.nan)
                stack.append(g)
                ax.plot(tw, fr, color=SERIES[0], alpha=0.18, linewidth=0.8)
            ax.plot(grid, np.nanmedian(np.array(stack), axis=0), color=SERIES[0], linewidth=2.0)
            ax.axhline(1.0, color=MUTED, linewidth=0.8, linestyle=(0, (3, 3)))
            ax.set_title(f'genlik {amp} m/s  (n={len(curves[amp])})', color=INK, fontsize=9)
            ax.set_xlabel('basamaktan sonra [s]', color=INK2)
        axes[0].set_ylabel('normalize yanıt (Gazebo hızı)', color=INK2)
        fig.suptitle('K5 tesis testi: komut basamağına dikey hız yanıtı (ince: tek basamak, kalın: ortanca)',
                     color=INK, fontsize=10, x=0.01, ha='left')
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        fig.savefig(os.path.join(out, 'tesis_basamak.png'), dpi=110, facecolor=SURFACE)
        plt.close(fig)


if __name__ == '__main__':
    main()
