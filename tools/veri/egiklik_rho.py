#!/usr/bin/env python3
"""Tilt and rho, from the recorded K1 and K3 episodes (no new flights).

    tools/veri/egiklik_rho.py [--kok ~/eland_veri] [--cikti DIR]

1. rho (measured, clean mask) minus rho_hesap (= A_gercek / (4.22 h_kamera^2),
   the geometric value for a level camera), split by the camera's tilt at the
   capture stamp: tilt = arccos(cos(roll) cos(pitch)), the angle between the
   body z axis and the vertical. roll / pitch are not in maske_olaylari.csv;
   they come from duzenli.csv (vehicle_attitude, 50 Hz grid) and are
   interpolated to t_yakalama. Only frames where rho_hesap means something:
   view_bounded = 1 (region does not touch the frame edge) and rho > 0.
2. Per episode: share of frames whose centre pixel is not a safe class
   (merkez_sinif not in {0, 1}) and rho = 0; whole recording and VALIDATE
   (durum = 2 at the capture stamp). Also counts the frames where the centre
   is unsafe but rho != 0 (should be none: detector_node sets rho = 0 then).
"""
import argparse
import csv
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dogrula import load_csv  # noqa: E402

SAFE = (0, 1)


def stats(x):
    x = x[np.isfinite(x)]
    if not x.size:
        return dict(n=0, ort=np.nan, ortanca=np.nan, rms=np.nan, p95=np.nan)
    return dict(n=int(x.size), ort=float(x.mean()), ortanca=float(np.median(x)),
                rms=float(np.sqrt(np.mean(x ** 2))), p95=float(np.percentile(np.abs(x), 95)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    p.add_argument('--cikti', default=None)
    a = p.parse_args()
    eps = sorted(glob.glob(os.path.join(a.kok, 'k1_*', '*', '*')) +
                 glob.glob(os.path.join(a.kok, 'k3_*', '*', '*')))
    fark = {}            # (kol grubu, bin) -> list of rho - rho_hesap
    rel = {}             # same, rho / rho_hesap - 1
    egim_val = {}        # kol grubu -> tilts in VALIDATE (all frames)
    per_ep = []
    for ep in eps:
        if not os.path.exists(os.path.join(ep, 'ep_ozet.json')):
            continue
        oz = json.load(open(os.path.join(ep, 'ep_ozet.json')))
        grup = 'K1' if oz['kol'].startswith('k1') else 'K3'
        m = load_csv(os.path.join(ep, 'maske_olaylari.csv'))
        d = load_csv(os.path.join(ep, 'duzenli.csv'))
        t = m['t_yakalama']
        roll = np.interp(t, d['t_gz'], d['roll'])
        pitch = np.interp(t, d['t_gz'], d['pitch'])
        tilt = np.degrees(np.arccos(np.clip(np.cos(roll) * np.cos(pitch), -1, 1)))
        # state at capture: last grid value at or before t (zero-order hold)
        idx = np.clip(np.searchsorted(d['t_gz'], t, side='right') - 1, 0, len(d['t_gz']) - 1)
        durum = d['durum'][idx]
        val = durum == 2
        egim_val.setdefault(grup, []).extend(tilt[val].tolist())
        ok = (m['view_bounded'] == 1) & (m['rho'] > 0) & np.isfinite(m['rho_hesap'])
        for aralik, rs in (('tum', ok), ('VALIDATE', ok & val)):
            for b, sel in (('< 5', rs & (tilt < 5)), ('>= 5', rs & (tilt >= 5))):
                fark.setdefault((grup, aralik, b), []).extend((m['rho'] - m['rho_hesap'])[sel].tolist())
                rel.setdefault((grup, aralik, b), []).extend(
                    (m['rho'][sel] / m['rho_hesap'][sel] - 1).tolist())
        unsafe = ~np.isin(m['merkez_sinif'], SAFE)
        z = unsafe & (m['rho'] == 0)
        # On W5 the data mode never hands over, so the mode is still in
        # VALIDATE after touchdown: count VALIDATE frames before touchdown too.
        tt = oz.get('t_temas_gercek')
        vo = val & (t < tt) if tt is not None else val
        per_ep.append(dict(
            ep_id=oz['ep_id'], kol=oz['kol'], dunya=oz['dunya_id'],
            kare=int(t.size), merkez_guvensiz_rho0=int(z.sum()),
            oran=float(z.mean()) if t.size else np.nan,
            kare_validate=int(val.sum()), merkez_guvensiz_rho0_validate=int((z & val).sum()),
            oran_validate=float((z & val).sum() / val.sum()) if val.any() else np.nan,
            kare_validate_temas_oncesi=int(vo.sum()),
            merkez_guvensiz_rho0_validate_temas_oncesi=int((z & vo).sum()),
            oran_validate_temas_oncesi=float((z & vo).sum() / vo.sum()) if vo.any() else np.nan,
            merkez_guvensiz_rho_sifirdan_farkli=int((unsafe & (m['rho'] != 0)).sum())))

    out = ['## D1. rho - rho_hesap, egiklige gore (view_bounded = 1, rho > 0)\n',
           '| kol | aralik | egiklik (derece) | kare | ort | ortanca | RMS | p95 abs | ort goreli (rho/rho_hesap - 1) | ortanca goreli |',
           '|---|---|---|---|---|---|---|---|---|---|']
    for key in sorted(fark):
        s = stats(np.array(fark[key]))
        r = stats(np.array(rel[key]))
        out.append(f"| {key[0]} | {key[1]} | {key[2]} | {s['n']} | {s['ort']:+.4f} | {s['ortanca']:+.4f} | "
                   f"{s['rms']:.4f} | {s['p95']:.4f} | {r['ort']:+.3f} | {r['ortanca']:+.3f} |")
    out.append('\n## D1b. VALIDATE icinde egiklik dagilimi (butun kareler)\n')
    out.append('| kol | kare | ortanca | p95 | en cok | >= 5 derece orani |')
    out.append('|---|---|---|---|---|---|')
    for g, v in sorted(egim_val.items()):
        v = np.array(v)
        out.append(f'| {g} | {v.size} | {np.median(v):.2f} | {np.percentile(v, 95):.2f} | '
                   f'{v.max():.2f} | {np.mean(v >= 5):.3f} |')
    out.append('\n## D2. Merkez piksel guvenli degil ve rho = 0 olan kare orani (bolum basina; tam liste CSV\'de)\n')
    out.append('| kol | bolum | oran ortanca (tum) | oran en cok (tum) | oran ortanca (VALIDATE) | oran en cok (VALIDATE) | VALIDATE orani > 0 olan bolum | en cok (VALIDATE, temastan once) | temastan once > 0 olan bolum | merkez guvensiz ama rho != 0 kare |')
    out.append('|---|---|---|---|---|---|---|---|---|---|')
    for g in ('K1', 'K3'):
        rows = [r for r in per_ep if (r['kol'].startswith('k1') if g == 'K1' else r['kol'].startswith('k3'))]
        o = np.array([r['oran'] for r in rows])
        ov = np.array([r['oran_validate'] for r in rows])
        ovo = np.array([r['oran_validate_temas_oncesi'] for r in rows])
        out.append(f"| {g} | {len(rows)} | {np.nanmedian(o):.3f} | {np.nanmax(o):.3f} | {np.nanmedian(ov):.3f} | "
                   f"{np.nanmax(ov):.3f} | {int(np.sum(ov > 0))} | {np.nanmax(ovo):.3f} | {int(np.sum(ovo > 0))} | "
                   f"{sum(r['merkez_guvensiz_rho_sifirdan_farkli'] for r in rows)} |")
    nz = [r for r in per_ep if r['oran_validate'] and r['oran_validate'] > 0]
    if nz:
        out.append('\nVALIDATE icinde orani > 0 olan bolumler:\n')
        out.append('| bolum | VALIDATE karesi | merkez guvensiz ve rho = 0 | oran | temastan once: kare | temastan once: merkez guvensiz ve rho = 0 | temastan once: oran |')
        out.append('|---|---|---|---|---|---|---|')
        for r in sorted(nz, key=lambda r: -r['oran_validate']):
            out.append(f"| {r['ep_id']} | {r['kare_validate']} | {r['merkez_guvensiz_rho0_validate']} | "
                       f"{r['oran_validate']:.3f} | {r['kare_validate_temas_oncesi']} | "
                       f"{r['merkez_guvensiz_rho0_validate_temas_oncesi']} | {r['oran_validate_temas_oncesi']:.3f} |")
    text = '\n'.join(out)
    print(text)
    if a.cikti:
        os.makedirs(a.cikti, exist_ok=True)
        open(os.path.join(a.cikti, 'egiklik_rho.md'), 'w').write(text + '\n')
        with open(os.path.join(a.cikti, 'merkez_guvensiz_rho0_bolum.csv'), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(per_ep[0].keys()))
            w.writeheader()
            w.writerows(per_ep)


if __name__ == '__main__':
    main()
