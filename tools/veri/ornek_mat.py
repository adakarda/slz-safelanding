#!/usr/bin/env python3
"""A small, representative MATLAB set: one .mat (v7, compressed) and one
short data dictionary per episode, plus a README.

    tools/veri/ornek_mat.py --cikti DIR EP_DIR [EP_DIR ...]

Each <ep_id>.mat holds, with the recorder's own column names:
  duzenli   struct of column vectors, 50 Hz grid (duzenli.csv)
  maske     struct, one row per mask (maske_olaylari.csv)
  karar     struct, one row per landing candidate (karar_olaylari.csv)
  gecis     struct, state transitions (t_gz numeric; onceki/sonraki/neden cell)
  bilgi     struct: episode id, arm, world, seed, policy, disturber, wind,
            takeoff altitude and the key instants from ep_ozet.json
  ozet_json, kosul_yaml   the episode's summary and conditions, as text
The four text columns that repeat on every duzenli row (ep_id, dunya_id,
tohum, kol) are moved into `bilgi`; nothing else is renamed or dropped.
"""
import argparse
import csv
import json
import os
import re
import sys

import numpy as np
import scipy.io as sio
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEXT_COLS = ('ep_id', 'dunya_id', 'tohum', 'kol')
SOZLUK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_dictionary.md')
KARAR = {
    't_alma': ('s', 'adayin kaydediciye ulastigi sim zamani'),
    't_damga': ('s', 'adayin dayandigi haritanin damgasi'),
    'gecerli': ('0/1', 'aday gecerli mi'),
    'aday_id': ('-', 'aday numarasi'),
    'x_yerel': ('m', 'aday konumu, harita = PX4 yerel ENU, dogu'),
    'y_yerel': ('m', 'aday konumu, harita = PX4 yerel ENU, kuzey'),
    'radius_m': ('m', 'secilen noktaya sigan dairenin yaricapi'),
    'area_m2': ('m2', 'bagli guvenli bolgenin alani; 40x40 m haritayla sinirli'),
    'area_ratio': ('-', 'modun kullandigi rho (adayla ~1.8 Hz gelir)'),
    'view_bounded': ('0/1', 'bolge kare kenarina degmiyor'),
    'risk': ('-', 'risk puani, 0 en guvenli'),
    'secilen_nokta_hata_m': ('m', 'adayin dunya konumu ile hedef yuzey merkezi arasi'),
}


def read_table(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}, []
    cols = list(rows[0].keys())
    out = {}
    for c in cols:
        vals = [r[c] for r in rows]
        try:
            out[c] = np.array([float(v) if v not in ('', None) else np.nan for v in vals])
        except ValueError:
            out[c] = np.array(vals, dtype=object)
    return out, cols


def dictionary():
    """Column -> (unit, note) from data_dictionary.md's tables."""
    d = {}
    for line in open(SOZLUK, encoding='utf-8'):
        if not line.startswith('|') or line.startswith('|---') or 'Sütun' in line:
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 3:
            continue
        names = [n.strip().strip('`') for n in cells[0].split(',')]
        if len(cells) == 4:      # duzenli: name | unit | source | note
            unit, note = cells[1], (cells[3] or cells[2])
        else:                    # maske: name | unit | note
            unit, note = cells[1], cells[2]
        for n in names:
            if '/' in n and n.startswith('bbox'):
                for s in ('x0', 'x1', 'y0', 'y1'):
                    d[f'bbox_{s}'] = (unit, note)
            else:
                d[n] = (unit, note)
    return d


def short(note, n=150):
    note = re.sub(r'\*\*', '', note)
    return note if len(note) <= n else note[:n - 1] + '…'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--cikti', required=True)
    p.add_argument('eps', nargs='+')
    a = p.parse_args()
    os.makedirs(a.cikti, exist_ok=True)
    sz = dictionary()
    index = []
    for ep in a.eps:
        oz = json.load(open(os.path.join(ep, 'ep_ozet.json')))
        kosul_txt = open(os.path.join(ep, 'kosul.yaml')).read()
        kosul = yaml.safe_load(kosul_txt)
        duz, duz_cols = read_table(os.path.join(ep, 'duzenli.csv'))
        msk, msk_cols = read_table(os.path.join(ep, 'maske_olaylari.csv'))
        kar, kar_cols = read_table(os.path.join(ep, 'karar_olaylari.csv'))
        gec, _ = read_table(os.path.join(ep, 'durum_gecisleri.csv'))
        duz_num = {c: v for c, v in duz.items() if c not in TEXT_COLS}
        bilgi = {
            'ep_id': oz['ep_id'], 'kol': oz.get('kol', ''), 'dunya': oz.get('dunya_id', ''),
            'tohum': float(oz.get('tohum', -1)),
            'politika': kosul.get('politika') or '', 'bozucu': kosul.get('bozucu') or '',
            'model': kosul.get('model') or '', 'ruzgar_mps': float(kosul.get('ruzgar_mps') or 0.0),
            'baslangic_irtifasi_m': float(kosul.get('baslangic_irtifasi_m') or np.nan),
            'ek_parametreler': kosul.get('ek_parametreler') or '',
        }
        for k in ('t_mod_devrede', 't_validate', 't_commit', 't_temas_gercek', 't_px4_landed',
                  'temas_dikey_hiz_gercek_hesap_mps', 'commit_h_ekf_m', 'commit_h_gercek_hedef_m'):
            v = oz.get(k)
            bilgi[k] = float(v) if v is not None else np.nan
        bilgi['basarili'] = float(bool(oz.get('basarili')))
        data = {
            'duzenli': duz_num, 'maske': msk, 'karar': kar,
            'gecis': {k: (v if v.dtype != object else v.astype(object)) for k, v in gec.items()},
            'bilgi': bilgi,
            'ozet_json': json.dumps(oz, ensure_ascii=False),
            'kosul_yaml': kosul_txt,
        }
        mat = os.path.join(a.cikti, f"{oz['ep_id']}.mat")
        sio.savemat(mat, data, do_compression=True, oned_as='column', long_field_names=True)

        # read it back: every column there, same length, same NaN count
        back = sio.loadmat(mat, squeeze_me=True, struct_as_record=False)
        problems = []
        for name, src in (('duzenli', duz_num), ('maske', msk), ('karar', kar)):
            if not src:
                continue
            s = back[name]
            for c, v in src.items():
                bv = np.atleast_1d(getattr(s, c))
                if bv.shape[0] != v.shape[0]:
                    problems.append(f'{name}.{c} boy {bv.shape[0]} != {v.shape[0]}')
                elif v.dtype != object and int(np.isnan(bv.astype(float)).sum()) != int(np.isnan(v).sum()):
                    problems.append(f'{name}.{c} NaN sayisi farkli')
        size_kb = os.path.getsize(mat) / 1024
        index.append((oz['ep_id'], size_kb, len(duz_num), len(duz['t_gz']), len(msk_cols),
                      len(msk.get('t_yakalama', [])), len(kar_cols), len(kar.get('t_alma', [])),
                      problems))

        # per-episode dictionary
        L = [f"# {oz['ep_id']} — kısa veri sözlüğü\n",
             f"Dosya: `{oz['ep_id']}.mat` (MATLAB v7, sıkıştırılmış), {size_kb:.0f} KB.\n",
             '## Bölüm\n',
             f"- **Kol:** {bilgi['kol']}; **dünya:** {bilgi['dunya']}; **tohum:** {int(bilgi['tohum'])}; "
             f"**model:** {bilgi['model']}",
             f"- **Politika:** `{bilgi['politika'] or '—'}`; **bozucu:** `{bilgi['bozucu'] or '—'}`; "
             f"**rüzgâr:** {bilgi['ruzgar_mps']} m/s; **kalkış:** {bilgi['baslangic_irtifasi_m']} m",
             f"- **Ek parametreler:** `{bilgi['ek_parametreler'] or '—'}`",
             f"- **Anlar (sim s):** mod devrede {bilgi['t_mod_devrede']:.2f}, VALIDATE {bilgi['t_validate']:.2f}, "
             f"COMMIT {bilgi['t_commit']:.2f}, gerçek temas {bilgi['t_temas_gercek']:.2f}, "
             f"PX4 landed {bilgi['t_px4_landed']:.2f} (NaN = olmadı)",
             f"- **Temas hızı (Gazebo):** {bilgi['temas_dikey_hiz_gercek_hesap_mps']:.2f} m/s; "
             f"**başarılı:** {'evet' if bilgi['basarili'] else 'hayır'}"
             + (' (tanımlama bölümü, inmiyor)' if oz.get('kol', '').startswith('k5') else ''),
             '',
             '## Okuma\n',
             '```matlab',
             f"S = load('{oz['ep_id']}.mat');",
             'D = S.duzenli;  M = S.maske;  K = S.karar;  B = S.bilgi;',
             "plot(D.t_gz, D.vz_gercek_hesap, D.t_gz, D.v_cmd); xline(B.t_validate); xline(B.t_temas_gercek)",
             "ozet = jsondecode(S.ozet_json);",
             '```\n',
             '## Kurallar\n',
             '- Zaman `t_gz` / `t_yakalama`: simülasyon saniyesi. `duzenli` 50 Hz ızgara; her kanal son değeri tutar, '
             '`<ad>_yas_ms` o değerin yaşıdır.',
             '- Dikey hızlar **aşağı +**, yükseklikler **yukarı +**. `h_ekf` kalkış noktasına göre; gerçek yükseklik `h_gercek_hedef`.',
             '- `_hesap`: ölçülenden hesaplanan; `_tahmin`: varsayım içeren.',
             '- Analizi `t_temas_gercek`te kesin; PX4 `landed` gerçek temastan geç gelir.\n',
             '## Sütunlar\n']
        for name, cols in (('duzenli', [c for c in duz_cols if c not in TEXT_COLS]),
                           ('maske', msk_cols), ('karar', kar_cols)):
            if not cols:
                continue
            L.append(f'### {name}\n')
            L.append('| sütun | birim | anlam |')
            L.append('|---|---|---|')
            for c in cols:
                if c.endswith('_yas_ms'):
                    continue
                unit, note = (KARAR.get(c) if name == 'karar' else None) or sz.get(c, ('', ''))
                L.append(f'| {c} | {unit} | {short(note)} |')
            yas = [c for c in cols if c.endswith('_yas_ms')]
            if yas:
                L.append(f'\nAyrıca {len(yas)} yaş sütunu (`<ad>_yas_ms`, ms).\n')
        L.append('\nTam sözlük: `tools/veri/data_dictionary.md` (depo).')
        open(os.path.join(a.cikti, f"{oz['ep_id']}_sozluk.md"), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    R = ['# Örnek MATLAB seti\n',
         'Her bölüm için bir `.mat` (v7, sıkıştırılmış) ve yanında `<ep_id>_sozluk.md`. Sütun adları kaydedicinin '
         'adlarıyla aynı; `duzenli`deki tekrar eden 4 metin sütunu (ep_id, dunya_id, tohum, kol) `bilgi` yapısına alındı.\n',
         '| dosya | KB | duzenli: sütun × satır | maske: sütun × satır | karar: sütun × satır |',
         '|---|---|---|---|---|']
    for r in index:
        R.append(f'| {r[0]}.mat | {r[1]:.0f} | {r[2]} × {r[3]} | {r[4]} × {r[5]} | {r[6]} × {r[7]} |')
    R.append('\nÜretici: `tools/veri/ornek_mat.py`. Doğrulama: her dosya `scipy.io.loadmat` ile geri okundu; '
             'her sütunun satır sayısı ve NaN sayısı CSV ile aynı. MATLAB bu makinede yok, MATLAB\'da açılarak denenmedi.')
    open(os.path.join(a.cikti, 'BENIOKU.md'), 'w', encoding='utf-8').write('\n'.join(R) + '\n')
    for r in index:
        print(f'{r[0]}: {r[1]:.0f} KB, duzenli {r[2]}x{r[3]}, maske {r[4]}x{r[5]}, karar {r[6]}x{r[7]}, '
              f'sorun: {r[8] or "yok"}')


if __name__ == '__main__':
    main()
