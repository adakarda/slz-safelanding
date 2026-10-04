#!/usr/bin/env python3
"""Tur 3 A/B verification, from the runs under <kok>/_tur3_dogrulama.

    tools/veri/tur3_dogrula.py [--kok ~/eland_veri] [--cikti DIR]

1. Both parameters off (defaults): each new Kol 0 episode against the
   recorded one with the same id -- state sequence, COMMIT heights,
   touchdown speed, durations -- and /eland/rho message count (expect 0).
2. A on (detector_node.publish_rho): rate of /eland/rho, latency from the
   capture stamp to its arrival at the recorder, the detector's own addition
   (arrival of rho minus arrival of the same mask), and whether the published
   rho equals the recorder's rho for that mask.
3. B, forced early COMMIT (landing_altitude 10 m), off vs on: per episode the
   COMMIT entry, whether the area law ran in COMMIT, the commanded speed in
   COMMIT, the touchdown speed; per setting median and max touchdown speed.
4. B, the three K3 episodes that touched down hard, rerun with both settings.
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


def ozet(ep):
    return json.load(open(os.path.join(ep, 'ep_ozet.json')))


def gecisler(ep):
    with open(os.path.join(ep, 'durum_gecisleri.csv')) as f:
        return [r['sonraki'] for r in csv.DictReader(f)]


def f2(x, n=2):
    return '—' if x is None or (isinstance(x, float) and not np.isfinite(x)) else f'{x:.{n}f}'


def commit_profili(ep, oz):
    """Commanded speed and law in COMMIT, from the 50 Hz table."""
    d = load_csv(os.path.join(ep, 'duzenli.csv'))
    tc, tt = oz.get('t_commit'), oz.get('t_temas_gercek')
    if tc is None or tt is None:
        return None
    m = (d['t_gz'] >= tc + 0.1) & (d['t_gz'] <= tt)
    if not m.any():
        return None
    v = d['v_cmd'][m]
    h = d['h_gercek_hedef'][m]
    alan = d['aktif_girdi'][m]
    son = (d['t_gz'] > tt - 0.4) & (d['t_gz'] <= tt)
    return dict(v_giris=float(v[np.isfinite(v)][0]) if np.isfinite(v).any() else np.nan,
                v_son=float(np.nanmedian(d['v_cmd'][son])) if son.any() else np.nan,
                v_min=float(np.nanmin(v)), v_max=float(np.nanmax(v)),
                alan_orani=float(np.nanmean(alan == 1)),
                h_giris=float(h[0]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    p.add_argument('--cikti', default=None)
    a = p.parse_args()
    D = os.path.join(a.kok, '_tur3_dogrulama')
    out = []

    # 1. off == old behaviour
    out.append('## 1. Iki parametre kapali (varsayilan) -- kayitli Kol 0 ile\n')
    out.append('| bolum | durum dizisi ayni mi | COMMIT h_ekf kayitli / yeni (m) | COMMIT h_gercek kayitli / yeni (m) | '
               'temas hizi kayitli / yeni (m/s) | VALIDATE->landed kayitli / yeni (s) | /eland/rho mesaji |')
    out.append('|---|---|---|---|---|---|---|')
    for ep in sorted(glob.glob(os.path.join(D, 'kapali', 'kol0', '*', '*'))):
        name = os.path.basename(ep)
        dunya = os.path.basename(os.path.dirname(ep))
        eski = os.path.join(a.kok, 'kol0', dunya, name)
        if not os.path.exists(os.path.join(ep, 'ep_ozet.json')) or not os.path.exists(eski):
            out.append(f'| {name} | veri yok | | | | | |')
            continue
        o1, o2 = ozet(eski), ozet(ep)
        g1, g2 = gecisler(eski), gecisler(ep)
        out.append(f"| {name} | {'evet' if g1 == g2 else 'HAYIR: ' + '>'.join(g1) + ' / ' + '>'.join(g2)} | "
                   f"{f2(o1.get('commit_h_ekf_m'))} / {f2(o2.get('commit_h_ekf_m'))} | "
                   f"{f2(o1.get('commit_h_gercek_hedef_m'))} / {f2(o2.get('commit_h_gercek_hedef_m'))} | "
                   f"{f2(o1.get('temas_dikey_hiz_gercek_hesap_mps'))} / {f2(o2.get('temas_dikey_hiz_gercek_hesap_mps'))} | "
                   f"{f2(o1.get('alcalma_suresi_validate_landed_s'), 1)} / {f2(o2.get('alcalma_suresi_validate_landed_s'), 1)} | "
                   f"{o2.get('rho_yayini_sayisi', 'alan yok')} |")
    for ep in sorted(glob.glob(os.path.join(D, '[!_]*', 'kol0', '*', '*'))):
        f = os.path.join(ep, 'dugum_bilgi.txt')
        if os.path.exists(f):
            grup = ep.split(os.sep)[-4]
            out.append(f'\n`{grup}/{os.path.basename(ep)}/dugum_bilgi.txt` (bolum ortasinda alindi):\n')
            out.append('```')
            out.extend(line.rstrip() for line in open(f) if line.strip())
            out.append('```')

    # 2. A on
    out.append('\n## 2. A acik (detector_node.publish_rho = true)\n')
    out.append('| bolum | /eland/rho mesaji | maske | hiz tum / VALIDATE (Hz) | yakalama -> rho alma p50 / p90 (ms) | '
               'maske alma -> rho alma p50 / p90 (ms) | eslesen | max abs(rho_yayin - rho_kaydedici) | view_bounded uyusmayan | durum dizisi kayitliyla ayni mi |')
    out.append('|---|---|---|---|---|---|---|---|---|---|')
    tum1, tum2 = [], []
    for ep in sorted(glob.glob(os.path.join(D, 'a_acik', 'kol0', '*', '*'))):
        name = os.path.basename(ep)
        if not os.path.exists(os.path.join(ep, 'ep_ozet.json')):
            continue  # still flying
        f = os.path.join(ep, 'rho_yayini.csv')
        if not os.path.exists(f):
            out.append(f'| {name} | rho_yayini.csv yok | | | | | | | | |')
            continue
        r = load_csv(f)
        m = load_csv(os.path.join(ep, 'maske_olaylari.csv'))
        oz = ozet(ep)
        n = r['t_alma'].size
        sure = r['t_alma'].max() - r['t_alma'].min()
        tv, tc = oz.get('t_validate'), oz.get('t_commit') or oz.get('t_temas_gercek')
        inval = (r['t_yakalama'] >= tv) & (r['t_yakalama'] <= tc) if tv and tc else np.zeros(n, bool)
        hz_val = inval.sum() / (tc - tv) if tv and tc else np.nan
        lat1 = 1000 * (r['t_alma'] - r['t_yakalama'])
        idx = {round(t, 3): i for i, t in enumerate(m['t_yakalama'])}
        lat2, drho, dvb = [], [], 0
        for i in range(n):
            j = idx.get(round(r['t_yakalama'][i], 3))
            if j is None:
                continue
            lat2.append(1000 * (r['t_alma'][i] - m['t_alma'][j]))
            drho.append(abs(r['rho'][i] - m['rho'][j]))
            dvb += int(r['view_bounded'][i] != m['view_bounded'][j])
        lat2 = np.array(lat2)
        tum1.extend(lat1.tolist())
        tum2.extend(lat2.tolist())
        eski = os.path.join(a.kok, 'kol0', 'veri_w2', name)
        ayni = (gecisler(eski) == gecisler(ep)) if os.path.exists(eski) else None
        out.append(f"| {name} | {n} | {m['t_yakalama'].size} | {n / sure:.2f} / {hz_val:.2f} | "
                   f"{np.percentile(lat1, 50):.1f} / {np.percentile(lat1, 90):.1f} | "
                   f"{np.percentile(lat2, 50):.1f} / {np.percentile(lat2, 90):.1f} | {lat2.size}/{n} | "
                   f"{max(drho) if drho else float('nan'):.6f} | {dvb} | {'evet' if ayni else ('HAYIR' if ayni is False else '—')} |")
    if tum1:
        t1, t2 = np.array(tum1), np.array(tum2)
        out.append(f'\nUc bolum birlikte: yakalama -> rho alma p50 {np.percentile(t1, 50):.1f} ms, p90 {np.percentile(t1, 90):.1f} ms; '
                   f'maske alma -> rho alma p50 {np.percentile(t2, 50):.1f} ms, p90 {np.percentile(t2, 90):.1f} ms.')

    # 3. B forced early COMMIT
    out.append('\n## 3. B -- zorlanmis erken COMMIT (landing_altitude 10 m, W3, kalkis 18 m)\n')
    out.append('| ayar | bolum | COMMIT h_ekf / h_gercek (m) | COMMIT\'te alan yasasi orani | v_cmd COMMIT girisi / temastan once (m/s) | '
               'v_cmd COMMIT min-max | temas hizi (m/s) | basarili |')
    out.append('|---|---|---|---|---|---|---|---|')
    ozetler = {}
    for g, ad in (('b_kapali', 'kapali'), ('b_acik', 'acik')):
        hizlar = []
        for ep in sorted(glob.glob(os.path.join(D, g, 'kol0', '*', '*'))):
            if not os.path.exists(os.path.join(ep, 'ep_ozet.json')):
                continue  # still flying
            oz = ozet(ep)
            pr = commit_profili(ep, oz)
            v = oz.get('temas_dikey_hiz_gercek_hesap_mps')
            if v is not None:
                hizlar.append(v)
            out.append(f"| {ad} | {os.path.basename(ep)} | {f2(oz.get('commit_h_ekf_m'))} / {f2(oz.get('commit_h_gercek_hedef_m'))} | "
                       f"{f2(pr['alan_orani']) if pr else '—'} | {f2(pr['v_giris']) if pr else '—'} / {f2(pr['v_son']) if pr else '—'} | "
                       f"{f2(pr['v_min']) if pr else '—'}-{f2(pr['v_max']) if pr else '—'} | {f2(v)} | {oz.get('basarili')} |")
        ozetler[ad] = np.array(hizlar)
    out.append('\n| ayar | bolum | temas hizi ortanca (m/s) | temas hizi en buyuk (m/s) | en kucuk (m/s) |')
    out.append('|---|---|---|---|---|')
    for ad, h in ozetler.items():
        if h.size:
            out.append(f'| {ad} | {h.size} | {np.median(h):.2f} | {h.max():.2f} | {h.min():.2f} |')
        else:
            out.append(f'| {ad} | 0 | — | — | — |')

    # 4. B, the hard K3 episodes again
    out.append('\n## 4. B -- sert temasli 3 K3 bolumu, iki ayarla yeniden\n')
    out.append('| ayar | bolum | COMMIT h_gercek (m) | COMMIT\'ten onceki son gerekce | COMMIT\'te alan yasasi orani | temas hizi (m/s) | ilk ucustaki temas (m/s) |')
    out.append('|---|---|---|---|---|---|---|')
    for g, ad in (('k3_kapali', 'kapali'), ('k3_acik', 'acik')):
        for ep in sorted(glob.glob(os.path.join(D, g, 'k3_*', '*', '*'))):
            if not os.path.exists(os.path.join(ep, 'ep_ozet.json')):
                continue  # still flying
            oz = ozet(ep)
            pr = commit_profili(ep, oz)
            with open(os.path.join(ep, 'durum_gecisleri.csv')) as f:
                rows = list(csv.DictReader(f))
            once = [r['neden'] for r in rows if r['sonraki'] != 'COMMIT'][-1:] or ['']
            kol = ep.split(os.sep)[-3]
            ilk = os.path.join(a.kok, kol, os.path.basename(os.path.dirname(ep)), os.path.basename(ep))
            v0 = ozet(ilk).get('temas_dikey_hiz_gercek_hesap_mps') if os.path.exists(ilk) else None
            out.append(f"| {ad} | {os.path.basename(ep)} | {f2(oz.get('commit_h_gercek_hedef_m'))} | {once[0][:60]} | "
                       f"{f2(pr['alan_orani']) if pr else '—'} | {f2(oz.get('temas_dikey_hiz_gercek_hesap_mps'))} | {f2(v0)} |")

    text = '\n'.join(out)
    print(text)
    if a.cikti:
        os.makedirs(a.cikti, exist_ok=True)
        open(os.path.join(a.cikti, 'tur3_dogrula.md'), 'w').write(text + '\n')


if __name__ == '__main__':
    main()
