#!/usr/bin/env python3
"""One row per episode of the law comparison, and the grouped table (K16, K18).

    tools/veri/yasa_dilim_ozet.py KOK [--md RAPOR.md] [--csv SATIRLAR.csv]

KOK holds kosu.sh episodes (<kol>/<dunya>/<ep>/). Per episode (K18): group
(own VALIDATE geometry, tools/veri/w5_pencere.py; W5 only), the group of the
same seed's y_ekf run, borderline flag, law, touchdown speed, COMMIT h_yasa /
h_ekf, fallbacks before / after COMMIT, ExternalShutdown count, min RTF, mode
retries, and K9's check that the recordings' last lines are whole. A run
that did not finish is listed with its reason, never dropped.

Grouped table: W5 always split into pencereli / penceresiz, n in every cell.
Cells with n <= 3 are "calisiyor mu", not evidence (K8 c, K16).
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import statistics
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import w5_pencere  # noqa: E402

NAN = float('nan')


def _csv(yol):
    if not os.path.exists(yol):
        return None, None
    with open(yol, newline='') as f:
        r = list(csv.reader(f))
    return (r[0], r[1:]) if r else (None, [])


def son_satir_tam(yol):
    bas, satir = _csv(yol)
    if bas is None:
        return None
    return int(not satir or len(satir[-1]) == len(bas))


def fl(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return NAN


def yasa_adi(kos):
    ek = kos.get('ek_parametreler') or ''
    m = re.search(r'inis_yasasi=(\w+)', ek)
    if not m or 'inis_yasasi_secimi=true' not in ek:
        return 'kapali'
    y = m.group(1)
    if y == 'gozlemci':
        t = re.search(r'gozlemci_tipi=(\w+)', ek)
        kx = re.search(r'\.kx=([-\d.]+)', ek)
        kc = re.search(r'\.kc=([-\d.]+)', ek)
        tip = t.group(1) if t else 'sabit'
        y = 'kalman' if tip == 'kalman' else f'sabit{kx.group(1) if kx else "2.0"}/{kc.group(1) if kc else "-2.0"}'
    return y


def satir(ep):
    kos = yaml.safe_load(open(os.path.join(ep, 'kosul.yaml')))
    out = dict(bolum=os.path.basename(os.path.normpath(ep)), kol=kos.get('kol'), dunya=kos.get('dunya'),
               tohum=kos.get('tohum'), yasa=yasa_adi(kos))
    oz_yol = os.path.join(ep, 'ep_ozet.json')
    if not os.path.exists(oz_yol):
        out['durum'] = 'ep_ozet yok (kosu tamamlanmadi)'
        return out
    oz = json.load(open(oz_yol))
    out.update(durum='tamam', temas=fl(oz.get('temas_dikey_hiz_gercek_hesap_mps')),
               basarili_v10=oz.get('basarili_v10'),
               commit='var' if oz.get('t_commit') else 'yok',
               alcalma_s=(fl(oz.get('t_temas_gercek')) - fl(oz.get('t_validate'))))
    # COMMIT heights: the law's from the mode's status, else the EKF's
    bas, ys = _csv(os.path.join(ep, 'yasa_durumu.csv'))
    out['commit_h_ekf'] = fl(oz.get('commit_h_ekf_m'))
    out['commit_h_yasa'] = NAN
    if bas:
        i_k, i_hy, i_he = bas.index('kilitli'), bas.index('commit_h_yasa_m'), bas.index('commit_h_ekf_m')
        kil = [r for r in ys if r[i_k] == '1']
        if kil:
            out['commit_h_yasa'], out['commit_h_ekf'] = fl(kil[0][i_hy]), fl(kil[0][i_he])
    # fallbacks before / after COMMIT
    bas, ol = _csv(os.path.join(ep, 'olay.csv'))
    if bas:
        t_commit = next((fl(r[0]) for r in ol if r[2] == 'commit'), math.inf)
        yed = [fl(r[0]) for r in ol if r[2] == 'yedek_basladi']
        out['yedek_once'] = sum(1 for t in yed if t < t_commit)
        out['yedek_sonra'] = sum(1 for t in yed if t >= t_commit)
        out['olay_son_bitti'] = int(bool(ol) and ol[-1][2] == 'bitti')
    bas, gz = _csv(os.path.join(ep, 'gozlemci.csv'))
    if bas:
        rtf = [fl(r[bas.index('rtf')]) for r in gz]
        rtf = [v for v in rtf if math.isfinite(v)]
        out['min_rtf'] = min(rtf) if rtf else NAN
        ih, ik, ig = bas.index('h_gozlemci_m'), bas.index('h_kahin_m'), bas.index('gecerli')
        g2 = next((r for r in gz if r[ig] == '1' and fl(r[ik]) <= 2.0), None)
        out['h_hata_2m'] = fl(g2[ih]) - fl(g2[ik]) if g2 else NAN
        out['kullanilan_kare'] = max((int(fl(r[bas.index('kullanilan_kare')])) for r in gz
                                      if r[ig] == '1'), default=0)
        out['kilit'] = int(any(r[bas.index('kilitli')] == '1' for r in gz))
    pl = os.path.join(ep, 'pipeline.log')
    out['ext_shutdown'] = open(pl, errors='replace').read().count(
        'rclpy.executors.ExternalShutdownException') if os.path.exists(pl) else NAN
    rs = os.path.join(ep, 'run_sim.log')
    out['yeniden_deneme'] = len(re.findall(r'deneme [2-9]\)', open(rs, errors='replace').read())) \
        if os.path.exists(rs) else NAN
    out['son_satir_tam'] = int(all(v in (None, 1) for v in (
        son_satir_tam(os.path.join(ep, 'duzenli.csv')), son_satir_tam(os.path.join(ep, 'gozlemci.csv')),
        out.get('olay_son_bitti'))))
    if 'w5' in str(out['dunya']):
        p = w5_pencere.pencere(ep)
        out.update(grup=p.get('grup'), pay=p.get('pay'), sinirda=p.get('sinirda'),
                   sinirli_kare=p.get('sinirli_kare'), grup_olcum=p.get('grup_olcum'))
    else:
        out['grup'] = '—'
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('kok')
    p.add_argument('--md', default=None)
    p.add_argument('--csv', default=None)
    a = p.parse_args()
    eps = sorted(glob.glob(os.path.join(a.kok, '*', '*', '*', 'kosul.yaml')))
    S = [satir(os.path.dirname(e)) for e in eps]
    # the y_ekf run's group of the same seed, carried to every arm (K16)
    ekf_grup = {(s['dunya'], s['tohum']): s.get('grup') for s in S if s['kol'] == 'y_ekf'}
    for s in S:
        s['grup_y_ekf'] = ekf_grup.get((s['dunya'], s['tohum']), '')
        s['grup_farki'] = int(s.get('grup') not in ('—', None) and s['grup_y_ekf'] not in ('', None)
                              and s.get('grup') != s['grup_y_ekf'])
    alan = []
    for s in S:
        alan += [k for k in s if k not in alan]
    if a.csv:
        with open(a.csv, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=alan)
            w.writeheader()
            w.writerows(S)
    md = ['| dünya | grup | yasa | n | temas ortanca / en büyük (m/s) | v10 | COMMIT | ĥ − h @2 m ortanca | not |',
          '|---|---|---|---|---|---|---|---|---|']
    anahtar = sorted({(s['dunya'], s.get('grup_y_ekf') or s.get('grup'), s['yasa']) for s in S if s.get('durum') == 'tamam'},
                     key=lambda k: (str(k[0]), str(k[1]), str(k[2])))
    for d, g, y in anahtar:
        h = [s for s in S if s.get('durum') == 'tamam' and s['dunya'] == d and s['yasa'] == y
             and (s.get('grup_y_ekf') or s.get('grup')) == g]
        t = [s['temas'] for s in h if math.isfinite(s['temas'])]
        e2 = [s['h_hata_2m'] for s in h if math.isfinite(s.get('h_hata_2m', NAN))]
        # no kahin height in the recording (switch off, no gozlemci.csv): no cell
        e2_hucre = f'{statistics.median(e2):+.2f}' if e2 else '—'
        md.append(f"| {d} | {g} | {y} | {len(h)} | "
                  f"{statistics.median(t):.2f} / {max(t):.2f} | {sum(1 for s in h if s.get('basarili_v10'))}/{len(h)} | "
                  f"{sum(1 for s in h if s['commit'] == 'var')}/{len(h)} | "
                  f"{e2_hucre} | {'çalışıyor mu (n ≤ 3)' if len(h) <= 3 else ''} |"
                  if t else f"| {d} | {g} | {y} | {len(h)} | — | — | — | — | |")
    eksik = [s for s in S if s.get('durum') != 'tamam']
    md.append(f'\nTamamlanmayan koşu: {len(eksik)}' + ''.join(f"\n- {s['bolum']}: {s['durum']}" for s in eksik))
    metin = '\n'.join(md)
    print(metin)
    if a.md:
        open(a.md, 'w').write(metin + '\n')


if __name__ == '__main__':
    main()
