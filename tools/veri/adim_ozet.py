#!/usr/bin/env python3
"""Interim report of one batch step, from its toplu.sh log.

    tools/veri/adim_ozet.py GUNLUK [--kok ~/eland_veri]

Per (kol, world): episodes, successes / failures, measured wall time; a line
per failure with its reason; and for W5 the three numbers the task asks for
instead of the COMMIT altitude: whether COMMIT was entered, the touchdown
speed, and h_ekf - h_gercek_hedef at touchdown (all ground truth from
Gazebo).
"""
import argparse
import csv
import json
import os
import shlex
from collections import defaultdict

import numpy as np


def ep_dir_of(cmd, kok):
    toks = shlex.split(cmd)
    env = {}
    i = 0
    while i < len(toks) and '=' in toks[i] and not toks[i].startswith('tools/'):
        k, _, v = toks[i].partition('=')
        env[k] = v
        i += 1
    args = toks[i + 1:]
    tohum, kol, dunya = args[0], args[1], args[2]
    ep_id = f'{kol}_{dunya}_t{tohum}' + (f"_{env['EP_EK']}" if env.get('EP_EK') else '')
    return kol, dunya, os.path.join(kok, kol, dunya, ep_id)


def at(d, t, col):
    tt = np.array([float(x) for x in d['t_gz']])
    v = np.array([float(x) if x != '' else np.nan for x in d[col]])
    i = int(np.argmin(np.abs(tt - t)))
    return v[i]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('gunluk')
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    a = p.parse_args()
    groups = defaultdict(list)
    for line in open(a.gunluk):
        if '|' not in line:
            continue
        head, cmd = line.split('|', 1)
        secs = int(head.split()[2])
        rc = int(head.split('rc=')[1].split()[0])
        kol, dunya, ep = ep_dir_of(cmd.strip(), a.kok)
        oz = {}
        if os.path.exists(os.path.join(ep, 'ep_ozet.json')):
            oz = json.load(open(os.path.join(ep, 'ep_ozet.json')))
        groups[(kol, dunya)].append((ep, secs, rc, oz))

    print('| kol | dünya | bölüm | başarılı | başarısız | süre, ortanca (duvar) | temas hızı, ortanca (m/s) |')
    print('|---|---|---|---|---|---|---|')
    fails = []
    w5 = []
    total_s = 0
    for (kol, dunya), rows in sorted(groups.items()):
        ok = [r for r in rows if r[3].get('basarili')]
        bad = [r for r in rows if not r[3].get('basarili')]
        total_s += sum(r[1] for r in rows)
        v = [r[3].get('temas_dikey_hiz_gercek_hesap_mps') for r in rows]
        v = [x for x in v if x is not None]
        print(f'| {kol} | {dunya} | {len(rows)} | {len(ok)} | {len(bad)} | '
              f'{np.median([r[1] for r in rows]):.0f} s | '
              f'{np.median(v) if v else float("nan"):.2f} |')
        for ep, secs, rc, oz in bad:
            why = []
            if rc:
                why.append(f'cikis kodu {rc}')
            if not oz:
                why.append('ozet yok')
            else:
                if oz.get('kor_inis'):
                    why.append('kor inis (aday hic yok)')
                if oz.get('t_px4_landed') is None:
                    why.append('PX4 landed yok')
                if oz.get('temas_yeri_uygun') is False:
                    why.append('temas hedef disinda')
                if oz.get('abort_sayisi'):
                    why.append(f"ABORT x{oz['abort_sayisi']}")
                if oz.get('hold_sayisi'):
                    why.append(f"HOLD x{oz['hold_sayisi']}")
            fails.append((os.path.basename(ep), ', '.join(why) or 'bilinmiyor'))
        if dunya.startswith('veri_w5'):
            for ep, secs, rc, oz in rows:
                if not oz or oz.get('t_temas_gercek') is None:
                    w5.append((os.path.basename(ep), None, None, None, None))
                    continue
                with open(os.path.join(ep, 'duzenli.csv')) as f:
                    d = {k: [] for k in next(csv.reader([f.readline()]))}
                with open(os.path.join(ep, 'duzenli.csv')) as f:
                    rd = csv.DictReader(f)
                    d = {k: [] for k in rd.fieldnames}
                    for r in rd:
                        for k in d:
                            d[k].append(r[k])
                t = oz['t_temas_gercek']
                dh = at(d, t - 0.1, 'h_ekf') - at(d, t - 0.1, 'h_gercek_hedef')
                w5.append((os.path.basename(ep), oz.get('t_commit') is not None,
                           oz.get('temas_dikey_hiz_gercek_hesap_mps'), dh,
                           at(d, t - 0.1, 'v_ref')))
    print(f'\ntoplam duvar süresi: {total_s / 60:.1f} dk, '
          f'{sum(len(r) for r in groups.values())} bölüm')
    if fails:
        print('\nbaşarısız bölümler:')
        for name, why in fails:
            print(f'  {name}: {why}')
    if w5:
        print('\n| W5 bölümü | COMMIT girildi mi | temas hızı (m/s) | temasta h_ekf − h_gercek_hedef (m) | temastan hemen önce v_ref (m/s) |')
        print('|---|---|---|---|---|')
        for row in w5:
            name, com, v, dh, vr = row
            fmt = lambda x: '—' if x is None else (f'{x:.2f}' if isinstance(x, float) else str(x))
            print(f'| {name} | {fmt(com)} | {fmt(v)} | {fmt(dh)} | {fmt(vr)} |')


if __name__ == '__main__':
    main()
