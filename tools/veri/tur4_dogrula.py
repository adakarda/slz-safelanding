#!/usr/bin/env python3
"""Tur 4 madde 2: commit_irtifa_yasasi on by default (eland_params.yaml),
checked on Kol 0 -- the runs under <kok>/_tur4_dogrulama/{kapali,acik}.

    tools/veri/tur4_dogrula.py [--kok ~/eland_veri] [--cikti DIR]

kapali: emergency_landing_mode.commit_irtifa_yasasi=false (the old law);
acik: no override, the yaml default. The same conditions under both
(tools/veri/listeler/tur4_kol0_commit.txt).

1. The value each episode actually ran with, from its params.yaml, and
   whether the recorder wrote the touchdown levels (basari.py).
2. Per setting and world: episodes, touchdown speed median and max,
   touchdowns at or above 1.0 and 0.5 m/s, successes by basarili_v10 (the
   primary criterion), by the 0.5 level (not for W5, judged at 1.0 only)
   and by the old criterion.
3. Per condition, side by side: touchdown speed, the share of COMMIT spent on
   the area law (the only case where the setting changes the command), the
   commanded speed just before touchdown, basarili_v10, state sequences.
4. kapali against the dataset's Kol 0 episode of the same condition,
   recorded before the parameter existed.
"""
import argparse
import glob
import os
import re
import sys

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basari  # noqa: E402
from tur3_dogrula import commit_profili, f2, gecisler, ozet  # noqa: E402

AYARLAR = ('kapali', 'acik')


def grup(dunya):
    m = re.match(r'veri_w(\d)$', dunya)
    return f'W{m.group(1)}' if m else 'adalar'


def bolum(ep):
    oz = ozet(ep)
    pr = yaml.safe_load(open(os.path.join(ep, 'params.yaml')))
    v = oz.get('temas_dikey_hiz_gercek_hesap_mps')
    return dict(oz=oz, v=float(v) if v is not None and np.isfinite(float(v)) else None,
                param=pr['emergency_landing_mode']['ros__parameters'].get('commit_irtifa_yasasi'),
                seviye=basari.temas_seviyeleri(oz),
                kayitta_seviye=all(k in oz for k, _ in basari.TEMAS_SEVIYELERI),
                profil=commit_profili(ep, oz), gecis=gecisler(ep),
                w5=os.path.basename(os.path.dirname(ep)).startswith('veri_w5'))


def ozet_satiri(ad, ayar, rows):
    """basarili_v10 is the primary criterion and W5 is judged at the 1.0
    level only (Tur 4 decisions): W5 rows get no 0.5 numbers, and totals
    count the 0.5 level over the other worlds."""
    v = np.array([r['v'] for r in rows if r['v'] is not None])
    n_ok = sum(bool(r['oz'].get('basarili')) for r in rows)
    n10 = sum(r['seviye']['basarili_v10'] for r in rows)
    r05 = [r for r in rows if not r['w5']]
    if r05:
        v05 = np.array([r['v'] for r in r05 if r['v'] is not None])
        not05 = f' ({len(r05)} bölümde, W5 hariç)' if len(r05) < len(rows) else ''
        sert05 = f'{int((v05 >= 0.5).sum())}{not05}'
        ok05 = f"{sum(r['seviye']['basarili_v05'] for r in r05)}{not05}"
    else:
        sert05 = ok05 = 'uygulanmaz (W5)'
    return (f"| {ad} | {ayar} | {len(rows)} | {f2(float(np.median(v))) if v.size else '—'} | "
            f"{f2(float(v.max())) if v.size else '—'} | {int((v >= 1.0).sum())} | **{n10}** | "
            f'{sert05} | {ok05} | {n_ok} |')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    p.add_argument('--cikti', default=None)
    a = p.parse_args()
    D = os.path.join(a.kok, '_tur4_dogrulama')

    eps = {s: {} for s in AYARLAR}       # setting -> (dunya, ep_id) -> bolum
    for s in AYARLAR:
        for ep in sorted(glob.glob(os.path.join(D, s, 'kol0', '*', '*'))):
            if os.path.exists(os.path.join(ep, 'ep_ozet.json')):
                eps[s][(os.path.basename(os.path.dirname(ep)), os.path.basename(ep))] = bolum(ep)
    out = []

    out.append('## 1. Bölümlerin gerçekten koştuğu ayar (`params.yaml`)\n')
    out.append('| ayar | bölüm | commit_irtifa_yasasi = false | = true | yok | kaydedici temas seviyelerini yazmış |')
    out.append('|---|---|---|---|---|---|')
    for s in AYARLAR:
        rows = list(eps[s].values())
        out.append(f"| {s} | {len(rows)} | {sum(r['param'] is False for r in rows)} | "
                   f"{sum(r['param'] is True for r in rows)} | {sum(r['param'] is None for r in rows)} | "
                   f"{sum(r['kayitta_seviye'] for r in rows)} |")

    out.append('\n## 2. Ayar ve dünya başına temas hızı\n')
    out.append('| dünya | ayar | bölüm | temas hızı ortanca (m/s) | en büyük (m/s) | v ≥ 1.0 | '
               '**başarılı, v < 1.0 (birincil)** | v ≥ 0.5 | başarılı, v < 0.5 | başarılı (eski ölçüt) |')
    out.append('|---|---|---|---|---|---|---|---|---|---|')
    gruplar = sorted({grup(d) for s in AYARLAR for d, _ in eps[s]},
                     key=lambda g: (g == 'adalar', g))
    for g in gruplar + ['**tümü**']:
        for s in AYARLAR:
            rows = [r for (d, _), r in eps[s].items() if g == '**tümü**' or grup(d) == g]
            out.append(ozet_satiri(g, s, rows))

    out.append('\n## 3. Koşul başına, yan yana (kapalı / açık)\n')
    out.append('| koşul | temas hızı (m/s) | COMMIT\'te alan yasası payı | v_cmd temastan önce (m/s) | '
               'COMMIT h_gercek (m) | başarılı, v < 1.0 | durum dizisi aynı mı |')
    out.append('|---|---|---|---|---|---|---|')
    ciftler = ayni_cift = 0
    for key in sorted(set(eps['kapali']) | set(eps['acik']), key=lambda k: (grup(k[0]) == 'adalar', k)):
        k, c = eps['kapali'].get(key), eps['acik'].get(key)
        if k and c:
            ciftler += 1
            ayni_cift += k['gecis'] == c['gecis']

        def iki(fn):
            return ' / '.join(fn(r) if r else 'yok' for r in (k, c))
        ayni = '—' if not (k and c) else (
            'evet' if k['gecis'] == c['gecis']
            else 'HAYIR: ' + '>'.join(k['gecis']) + ' / ' + '>'.join(c['gecis']))
        out.append(f"| {key[1].replace('kol0_', '')} | {iki(lambda r: f2(r['v']))} | "
                   f"{iki(lambda r: f2(r['profil']['alan_orani']) if r['profil'] else '—')} | "
                   f"{iki(lambda r: f2(r['profil']['v_son']) if r['profil'] else '—')} | "
                   f"{iki(lambda r: f2(r['oz'].get('commit_h_gercek_hedef_m')))} | "
                   f"{iki(lambda r: 'evet' if r['seviye']['basarili_v10'] else 'hayır')} | {ayni} |")
    out.append(f'\nDurum dizisi kapalı ile açıkta aynı: {ayni_cift}/{ciftler}.')

    out.append('\n## 4. Kapalı, veri setindeki aynı koşulla (parametre yokken kaydedilmiş)\n')
    out.append('| koşul | durum dizisi aynı mı | temas hızı veri seti / kapalı (m/s) |')
    out.append('|---|---|---|')
    ayni_n = 0
    for (dunya, name), r in sorted(eps['kapali'].items(), key=lambda kv: (grup(kv[0][0]) == 'adalar', kv[0])):
        eski = os.path.join(a.kok, 'kol0', dunya, name)
        if not os.path.exists(os.path.join(eski, 'ep_ozet.json')):
            out.append(f'| {name} | veri setinde yok | |')
            continue
        g_eski = gecisler(eski)
        ayni_n += g_eski == r['gecis']
        v_eski = ozet(eski).get('temas_dikey_hiz_gercek_hesap_mps')
        out.append(f"| {name.replace('kol0_', '')} | "
                   f"{'evet' if g_eski == r['gecis'] else 'HAYIR: ' + '>'.join(g_eski) + ' / ' + '>'.join(r['gecis'])} | "
                   f'{f2(v_eski)} / {f2(r["v"])} |')
    out.append(f"\nDurum dizisi aynı: {ayni_n}/{len(eps['kapali'])}.")

    text = '\n'.join(out)
    print(text)
    if a.cikti:
        os.makedirs(a.cikti, exist_ok=True)
        with open(os.path.join(a.cikti, 'tur4_dogrula.md'), 'w') as f:
            f.write(text + '\n')


if __name__ == '__main__':
    main()
