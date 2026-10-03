#!/usr/bin/env python3
"""Check recorded episodes: completeness, alignment, touchdown, one figure each.

    tools/veri/dogrula.py EP_DIR [EP_DIR ...] [--cikti DIR]

Writes dogrulama.md (one table, numbers only) and <ep_id>.png per episode.
The figures are small multiples on one shared time axis -- one quantity per
panel, never two y-scales -- with time zero at the moment the mode engaged.
"""
import argparse
import csv
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Reference palette (dataviz skill, light mode), first three slots: validated
# all-pairs; aqua is under 3:1 on the surface, so every panel carries a legend.
SERIES = ('#2a78d6', '#eb6834', '#1baf7a')
SURFACE, INK, INK2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, BASE = '#e1e0d9', '#c3c2b7'
VALIDATE, COMMIT = 2, 5
SPEC_COLS = ('durum', 'h_ekf', 'vz_ekf', 'vx', 'vy', 'roll', 'pitch', 'yaw',
             'v_cmd', 'v_ref', 'I_hesap', 'aktif_girdi', 'h_gercek_zemin',
             'h_gercek_hedef', 'vz_gercek_hesap', 'yatay_hata_m')


def load_csv(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    out = {}
    for k in rows[0]:
        vals = [r[k] for r in rows]
        try:
            out[k] = np.array([float(v) if v != '' else np.nan for v in vals])
        except ValueError:
            out[k] = np.array(vals, dtype=object)
    return out


def rms(x):
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else float('nan')


def check(ep_dir):
    d = load_csv(os.path.join(ep_dir, 'duzenli.csv'))
    m = load_csv(os.path.join(ep_dir, 'maske_olaylari.csv'))
    oz = json.load(open(os.path.join(ep_dir, 'ep_ozet.json')))
    r = {'ep_id': oz['ep_id'], 'basarili': oz.get('basarili')}

    desc = np.isin(d['durum'], (VALIDATE, COMMIT))
    val = d['durum'] == VALIDATE
    r['dolu_min_%'] = min(100.0 * np.isfinite(d[c][desc]).mean() for c in SPEC_COLS
                          if c not in ('I_hesap', 'v_cmd')) if desc.any() else float('nan')
    r['v_cmd_dolu_%'] = 100.0 * np.isfinite(d['v_cmd'][desc]).mean() if desc.any() else float('nan')
    r['I_hesap_dolu_%'] = 100.0 * np.isfinite(d['I_hesap'][val]).mean() if val.any() else float('nan')

    air = d['h_gercek_zemin'] > 0.3
    dh = d['h_ekf'][air] - d['h_gercek_zemin'][air]
    r['h_ekf-h_gercek bias_m'] = float(np.nanmean(dh)) if air.any() else float('nan')
    r['h_ekf-h_gercek rms_m'] = rms(dh)
    r['vz_ekf-vz_gercek rms'] = rms(d['vz_ekf'][air] - d['vz_gercek_hesap'][air])
    r['takip rms (vz_ekf-v_ref, VALIDATE)'] = rms(d['vz_ekf'][val] - d['v_ref'][val])
    ih = d['I_hesap'][np.isfinite(d['I_hesap'])]
    r['I_hesap ortanca'] = float(np.median(ih)) if len(ih) else float('nan')
    r['|I_hesap| p95'] = float(np.percentile(np.abs(ih), 95)) if len(ih) else float('nan')
    yh = d['yatay_hata_m'][val]
    r['yatay hata ortanca_m (VALIDATE)'] = float(np.nanmedian(yh)) if np.isfinite(yh).any() else float('nan')

    if m:
        r['maske yasi p50_ms'] = float(np.median(m['maske_yasi_ms']))
        r['maske yasi p90_ms'] = float(np.percentile(m['maske_yasi_ms'], 90))
        t_val, t_com = oz.get('t_validate'), oz.get('t_commit')
        if t_val:
            inv = (m['t_yakalama'] >= t_val) & (m['t_yakalama'] <= (t_com or np.inf))
            r['rho ortanca (VALIDATE)'] = float(np.median(m['rho'][inv])) if inv.any() else float('nan')
            r['view_bounded % (VALIDATE)'] = 100.0 * float(np.mean(m['view_bounded'][inv])) if inv.any() else float('nan')
    for k in ('inis_suresi_mod_landed_s', 'temas_dikey_hiz_gercek_hesap_mps',
              'ground_contact_gecikmesi_s', 'landed_gecikmesi_s', 'commit_h_ekf_m',
              'commit_h_gercek_hedef_m', 'abort_sayisi', 'hold_sayisi',
              'aday_kayip_sayisi'):
        r[k] = oz.get(k)
    sk = {s['kanal']: s for s in oz.get('sureklilik', [])}
    for kanal in ('vehicle_local_position', 'gt_pose (damga)', 'maske (yakalama damgasi)',
                  'trajectory_setpoint', 'eland_state'):
        s = sk.get(kanal, {})
        r[f'{kanal} Hz / en uzun ms / kayip'] = (
            f"{s.get('hz', 'nan')} / {s.get('aralik_en_uzun_ms', 'nan')} / "
            f"{s.get('kayip_mesaj_tahmini', 'nan')}")
    return r, d, m, oz


def figure(ep_dir, d, m, oz, path):
    t0 = oz.get('t_mod_devrede') or d['t_gz'][0]
    t = d['t_gz'] - t0
    keep = t >= -5.0
    tm = m['t_yakalama'] - t0 if m else np.array([])
    km = tm >= -5.0 if m else np.array([], dtype=bool)

    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'axes.edgecolor': BASE, 'axes.labelcolor': INK2,
                         'xtick.color': MUTED, 'ytick.color': MUTED,
                         'text.color': INK})
    fig, axes = plt.subplots(5, 1, figsize=(9, 10.5), sharex=True, facecolor=SURFACE)
    panels = [
        ('Yükseklik [m]', [('h_ekf (EKF)', t, d['h_ekf']),
                           ('h_gercek_zemin (Gazebo)', t, d['h_gercek_zemin'])]),
        ('Komut, aşağı + [m/s]', [('v_ref (yasa)', t, d['v_ref']),
                                  ('v_cmd (PX4\'e giden)', t, d['v_cmd'])]),
        ('Ölçülen hız, aşağı + [m/s]', [('vz_ekf', t, d['vz_ekf']),
                                        ('vz_gercek_hesap (Gazebo türevi)', t, d['vz_gercek_hesap'])]),
        ('Kapsama oranı ρ', [('rho (maske başına)', tm, m['rho'] if m else [])]),
        ('Sınıf sınırı pikseli', [('sinif_siniri_piksel (maske başına)', tm,
                                   m['sinif_siniri_piksel'] if m else [])]),
    ]
    events = [('VALIDATE', oz.get('t_validate')), ('COMMIT', oz.get('t_commit')),
              ('temas', oz.get('t_temas_gercek')), ('landed', oz.get('t_px4_landed'))]
    for ax, (title, series) in zip(axes, panels):
        ax.set_facecolor(SURFACE)
        for spine in ('top', 'right'):
            ax.spines[spine].set_visible(False)
        ax.grid(True, axis='y', color=GRID, linewidth=0.6)
        for i, (label, x, y) in enumerate(series):
            x = np.asarray(x, float)
            y = np.asarray(y, float)
            sel = keep if len(x) == len(t) else km
            ax.plot(x[sel], y[sel], color=SERIES[i], linewidth=1.6, label=label)
        for name, te in events:
            if te:
                ax.axvline(te - t0, color=MUTED, linewidth=0.8, linestyle=(0, (3, 3)))
        ax.set_ylabel(title, color=INK2)
        if len(series) > 1:
            ax.legend(loc='upper right', frameon=False, fontsize=8)
    top = axes[0]
    for name, te in events:
        if te:
            top.annotate(name, (te - t0, 1.0), xycoords=('data', 'axes fraction'),
                         xytext=(2, 2), textcoords='offset points', color=INK2,
                         fontsize=8, rotation=90, va='bottom')
    axes[-1].set_xlabel('mod devreye girdikten sonra geçen süre [s] (sim saati)', color=INK2)
    fig.suptitle(f"{oz['ep_id']} — iniş {oz.get('inis_suresi_mod_landed_s') or float('nan'):.1f} s, "
                 f"temas hızı {oz.get('temas_dikey_hiz_gercek_hesap_mps') or float('nan'):.2f} m/s",
                 color=INK, fontsize=11, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(path, dpi=110, facecolor=SURFACE)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('eps', nargs='+')
    p.add_argument('--cikti', default=None)
    a = p.parse_args()
    out = a.cikti or os.path.dirname(os.path.abspath(a.eps[0]))
    os.makedirs(out, exist_ok=True)
    rows = []
    for ep in a.eps:
        r, d, m, oz = check(ep)
        figure(ep, d, m, oz, os.path.join(out, f"{oz['ep_id']}.png"))
        rows.append(r)
    keys = list(rows[0])
    with open(os.path.join(out, 'dogrulama.md'), 'w') as f:
        f.write('| ölçüt | ' + ' | '.join(str(r['ep_id']) for r in rows) + ' |\n')
        f.write('|---|' + '---|' * len(rows) + '\n')
        for k in keys[1:]:
            cells = []
            for r in rows:
                v = r.get(k)
                cells.append(f'{v:.3g}' if isinstance(v, float) else str(v))
            f.write(f'| {k} | ' + ' | '.join(cells) + ' |\n')
    print(open(os.path.join(out, 'dogrulama.md')).read())


if __name__ == '__main__':
    main()
