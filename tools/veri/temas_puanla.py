#!/usr/bin/env python3
"""Rescore the recorded episodes with the touchdown-speed levels (Tur 4,
madde 4) and report them. No new runs: everything comes from ep_ozet.json.

    tools/veri/temas_puanla.py [--kok ~/eland_veri] [--cikti DIR] [--yalniz-rapor]

Adds basarili_v05 / basarili_v10 (basari.py) to the ep_ozet.json of every
dataset episode -- the ones birlestir.py puts in tum_ozet.csv -- and leaves
every other field as it was; --yalniz-rapor writes nothing. Then, per arm
(kol) and per world for Kol 0: episodes, successes by the old criterion and
by each level, touchdown speed median and max, and how many touched down at
or above 0.5 and 1.0 m/s; and the episodes each level takes off the success
list. ep.mat keeps the summary it was recorded with (ozet_json): the new
fields are in ep_ozet.json, tum_ozet.csv and birlesik_*.mat.
"""
import argparse
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basari  # noqa: E402
from birlestir import SKIP  # noqa: E402


def bolumler(kok):
    """(kol, dunya, ep_dir) of the dataset episodes, as birlestir.py finds them."""
    for p in sorted(glob.glob(os.path.join(kok, '*', '*', '*', 'ep_ozet.json'))):
        rel = os.path.relpath(p, kok).split(os.sep)
        if rel[0] in SKIP or rel[0].startswith('_'):
            continue
        yield rel[0], rel[1], os.path.dirname(p)


def hiz(oz):
    v = oz.get('temas_dikey_hiz_gercek_hesap_mps')
    return float(v) if v is not None and np.isfinite(float(v)) else None


def satir(ad, rows):
    v = np.array([r['v'] for r in rows if r['v'] is not None])
    n_ok = sum(r['basarili'] for r in rows)
    n10 = sum(r['basarili_v10'] for r in rows)
    n05 = sum(r['basarili_v05'] for r in rows)
    med = f'{np.median(v):.2f}' if v.size else '—'
    mx = f'{v.max():.2f}' if v.size else '—'
    return (f'| {ad} | {len(rows)} | {v.size} | {n_ok} | {n10} | {n05} | {med} | {mx} | '
            f'{int((v >= 0.5).sum())} | {int((v >= 1.0).sum())} |')


BASLIK = ('| {} | bölüm | temas hızı olan | başarılı (eski ölçüt) | başarılı ve v < 1.0 | '
          'başarılı ve v < 0.5 | temas hızı ortanca (m/s) | en büyük (m/s) | v ≥ 0.5 | v ≥ 1.0 |\n'
          '|---|---|---|---|---|---|---|---|---|---|')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    p.add_argument('--cikti', default=None)
    p.add_argument('--yalniz-rapor', action='store_true')
    a = p.parse_args()

    rows, yazilan = [], 0
    for kol, dunya, ep in bolumler(a.kok):
        path = os.path.join(ep, 'ep_ozet.json')
        oz = json.load(open(path))
        yeni = basari.temas_seviyeleri(oz)
        if not a.yalniz_rapor and any(oz.get(k) != val for k, val in yeni.items()):
            oz.update(yeni)
            with open(path, 'w') as f:
                json.dump(oz, f, indent=2, ensure_ascii=False, default=float)
            yazilan += 1
        ks = {}
        if os.path.exists(os.path.join(ep, 'kosul.yaml')):
            ks = yaml.safe_load(open(os.path.join(ep, 'kosul.yaml'))) or {}
        rows.append(dict(ep_id=os.path.basename(ep), kol=kol, dunya=dunya, v=hiz(oz),
                         basarili=bool(oz.get('basarili')), **yeni,
                         beklenen=kol.startswith('k5') or bool(ks.get('negatif_ornek'))))

    out = [f'# Temas hızıyla yeniden puanlama ({len(rows)} bölüm, yeni koşu yok)\n',
           f'`basarili` değişmedi; yanına `basarili_v10` (başarılı ve temas hızı < 1.0 m/s) ve '
           f'`basarili_v05` (< 0.5 m/s) eklendi (`tools/veri/basari.py`). Temas hızı: '
           f'Gazebo yüksekliğinin ilk kez 3 cm altına indiği andan önceki 0.3 s\'deki en büyük '
           f'aşağı hız. Ortanca, en büyük ve v ≥ sayıları gruptaki temas hızı ölçülen bütün '
           f'bölümlerden (başarısızlar dahil). ep_ozet.json\'u güncellenen: '
           f'{"yazılmadı (--yalniz-rapor)" if a.yalniz_rapor else yazilan}.\n']

    out.append('## Kol başına\n')
    out.append(BASLIK.format('kol'))
    by_kol = defaultdict(list)
    for r in rows:
        by_kol[r['kol']].append(r)
    for kol in sorted(by_kol):
        out.append(satir(kol, by_kol[kol]))
    out.append(satir('**toplam**', rows))
    out.append(satir('**toplam, K5/K5r ve negatifler hariç**', [r for r in rows if not r['beklenen']]))
    out.append('\nK5/K5r tanımlama bölümleri inmiyor (temas yok); negatif örneklerde '
               'başarısızlık beklenen.\n')

    out.append('## Kol 0, dünya başına\n')
    out.append(BASLIK.format('dünya'))
    by_dunya = defaultdict(list)
    for r in by_kol.get('kol0', []):
        by_dunya[r['dunya']].append(r)
    for d in sorted(by_dunya):
        out.append(satir(d, by_dunya[d]))

    dusen = [r for r in rows if r['basarili'] and not r['basarili_v05']]
    out.append(f'\n## Seviyelerin başarı listesinden çıkardığı bölümler ({len(dusen)})\n')
    out.append('| bölüm | kol | dünya | temas hızı (m/s) | v < 1.0 | v < 0.5 |')
    out.append('|---|---|---|---|---|---|')
    for r in sorted(dusen, key=lambda r: -(r['v'] or 0)):
        v = '—' if r['v'] is None else f"{r['v']:.3f}"
        out.append(f"| {r['ep_id']} | {r['kol']} | {r['dunya']} | {v} | "
                   f"{'evet' if r['basarili_v10'] else 'HAYIR'} | HAYIR |")

    text = '\n'.join(out)
    print(text)
    if a.cikti:
        os.makedirs(a.cikti, exist_ok=True)
        with open(os.path.join(a.cikti, 'temas_puanla.md'), 'w') as f:
            f.write(text + '\n')


if __name__ == '__main__':
    main()
