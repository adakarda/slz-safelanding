#!/usr/bin/env python3
"""Assemble the dataset (Asama 6): tum_ozet.csv, a seed-based split and the
merged MATLAB files.

    tools/veri/birlestir.py [--kok ~/eland_veri]

Split, 70 / 15 / 15 by a stable hash, never by random draw, so an episode
recorded tomorrow lands in the same split as today's with the same key:
  * random island worlds (veri_ada_tNNNN[_rX]): the whole island is one key --
    a test island is never seen in training, under any pattern or wind;
  * every other world: the key is world + episode seed.
Test episodes are linked under <kok>/_bolme/test/ with their own merged file;
nothing in train/val points into it.

Writes:
  <kok>/tum_ozet.csv                 one row per episode, with its split
  <kok>/_bolme/<split>/<ep_id>       links to the episode folders
  <kok>/_bolme/<split>/birlesik_<split>.mat
      ep      per-episode table (ep_idx is the row index, 1-based in MATLAB
              terms: ep_idx 0 here = first row)
      duzenli, maske, karar   all episodes' tables concatenated, numeric
              columns only (float32), with an ep_idx column
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys

import numpy as np
import scipy.io
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basari  # noqa: E402

SKIP = {'dogrulama', 'dunyalar', '_bolme'}
OZET_COLS = ['ep_id', 'kol', 'dunya', 'tohum', 'bolme', 'negatif_ornek', 'model',
             'ruzgar_mps', 'politika', 'bozucu', 'commit_irtifa_yasasi', 'basarili',
             'basarili_v05', 'basarili_v10', 'temas_yeri_uygun',
             'kor_inis', 'inis_suresi_mod_landed_s', 'alcalma_suresi_validate_landed_s',
             't_temas_gercek', 'temas_dikey_hiz_gercek_hesap_mps',
             'ground_contact_gecikmesi_s', 'landed_gecikmesi_s', 'commit_h_ekf_m',
             'commit_h_gercek_hedef_m', 'abort_sayisi', 'hold_sayisi',
             'aday_kayip_sayisi', 'aday_kayip_toplam_s', 'kayit_suresi_s', 'yol']


def commit_yasasi(ep_dir):
    """commit_irtifa_yasasi the episode flew with, from its params.yaml; false
    when the file or the key is missing (recorded before the parameter
    existed, i.e. the old law)."""
    path = os.path.join(ep_dir, 'params.yaml')
    if not os.path.exists(path):
        return False
    doc = yaml.safe_load(open(path)) or {}
    mod = (doc.get('emergency_landing_mode') or {}).get('ros__parameters') or {}
    return bool(mod.get('commit_irtifa_yasasi', False))


def split_of(dunya, tohum):
    m = re.match(r'(veri_ada_t\d+)', dunya)
    key = m.group(1) if m else f"{re.sub(r'_r[0-9p]+$', '', dunya)}:{tohum}"
    h = int(hashlib.sha1(key.encode()).hexdigest(), 16) % 100
    return 'train' if h < 70 else 'val' if h < 85 else 'test'


def read_csv_numeric(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    out = {}
    for k in rows[0]:
        try:
            out[k] = np.array([float(r[k]) if r[k] != '' else np.nan for r in rows],
                              dtype=np.float32)
        except ValueError:
            pass                              # string columns stay in the CSVs
    return out


def concat(tables):
    keys = sorted(set().union(*[t.keys() for t in tables])) if tables else []
    out = {}
    for k in keys:
        parts = []
        for t in tables:
            n = len(next(iter(t.values()))) if t else 0
            parts.append(t.get(k, np.full(n, np.nan, dtype=np.float32)))
        out[k] = np.concatenate(parts) if parts else np.array([], np.float32)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    a = p.parse_args()
    eps = []
    for oz_path in sorted(glob.glob(os.path.join(a.kok, '*', '*', '*', 'ep_ozet.json'))):
        rel = os.path.relpath(oz_path, a.kok).split(os.sep)
        if rel[0] in SKIP or rel[0].startswith('_'):
            continue
        ep_dir = os.path.dirname(oz_path)
        oz = json.load(open(oz_path))
        ks = {}
        if os.path.exists(os.path.join(ep_dir, 'kosul.yaml')):
            ks = yaml.safe_load(open(os.path.join(ep_dir, 'kosul.yaml'))) or {}
        dunya = rel[1]
        tohum = oz.get('tohum', ks.get('tohum'))
        row = {
            'ep_id': oz['ep_id'], 'kol': rel[0], 'dunya': dunya, 'tohum': tohum,
            'bolme': split_of(dunya, tohum),
            'negatif_ornek': ks.get('negatif_ornek', False),
            'model': ks.get('model', 'x500_seg_cam_down'),
            'ruzgar_mps': ks.get('ruzgar_mps', 0.0),
            'politika': ks.get('politika', ''), 'bozucu': ks.get('bozucu', ''),
            'commit_irtifa_yasasi': commit_yasasi(ep_dir),
            'yol': ep_dir,
            # from basarili and the touchdown speed, whether or not the
            # episode's ep_ozet.json was rescored
            **basari.temas_seviyeleri(oz),
        }
        for k in OZET_COLS:
            if k not in row:
                row[k] = oz.get(k)
        eps.append(row)

    with open(os.path.join(a.kok, 'tum_ozet.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=OZET_COLS)
        w.writeheader()
        for r in eps:
            w.writerow(r)

    for split in ('train', 'val', 'test'):
        d = os.path.join(a.kok, '_bolme', split)
        os.makedirs(d, exist_ok=True)
        for old in os.listdir(d):
            if os.path.islink(os.path.join(d, old)):
                os.remove(os.path.join(d, old))
        chosen = [r for r in eps if r['bolme'] == split]
        duz, msk, kar = [], [], []
        for i, r in enumerate(chosen):
            os.symlink(r['yol'], os.path.join(d, r['ep_id']))
            for store, name in ((duz, 'duzenli.csv'), (msk, 'maske_olaylari.csv'),
                                (kar, 'karar_olaylari.csv')):
                t = read_csv_numeric(os.path.join(r['yol'], name))
                if t:
                    n = len(next(iter(t.values())))
                    t['ep_idx'] = np.full(n, i, dtype=np.float32)
                    store.append(t)
        ep_table = {k: np.array([('' if r[k] is None else str(r[k])) for r in chosen],
                                dtype=object) for k in OZET_COLS}
        scipy.io.savemat(os.path.join(d, f'birlesik_{split}.mat'), {
            'ep': ep_table, 'duzenli': concat(duz), 'maske': concat(msk),
            'karar': concat(kar)}, do_compression=True, long_field_names=True)
        print(f'{split}: {len(chosen)} bolum -> {d}/birlesik_{split}.mat')
    print(f'tum_ozet.csv: {len(eps)} bolum')


if __name__ == '__main__':
    main()
