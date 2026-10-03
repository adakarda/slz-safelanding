#!/usr/bin/env python3
"""Fill in the touchdown fields of ep_ozet.json where the recorder left them
empty.

    tools/veri/ozet_yenile.py EP_DIR [EP_DIR ...]

For episodes recorded before the recorder anchored touchdown at the first
descent state (VALIDATE, or COMMIT straight from SEARCH): blind descents
(W1, negative islands) got no touchdown at all. Same rule as kaydedici.py,
on the 50 Hz table: first sample after min(t_validate, t_commit) with ground
truth height < 3 cm; speed = highest true descent rate in the 0.3 s before.
Episodes that already have a touchdown are not touched. The old values are
kept under 'onceki'.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dunya as dunya_mod  # noqa: E402
from dogrula import load_csv  # noqa: E402

TEMAS_ESIGI_M = 0.03  # kaydedici.py


def rising(t, flag, after):
    m = t > after
    f = flag[m] > 0.5
    idx = np.where(~f[:-1] & f[1:])[0]
    return float(t[m][idx[0] + 1]) if len(idx) else None


def main():
    for ep in sys.argv[1:]:
        p = os.path.join(ep, 'ep_ozet.json')
        oz = json.load(open(p))
        if oz.get('t_temas_gercek') is not None:
            # the recorder found it (on the raw ground-truth samples, which
            # this 50 Hz table only approximates): leave it alone
            print(f'{os.path.basename(ep)}: temas zaten var, dokunulmadi')
            continue
        d = load_csv(os.path.join(ep, 'duzenli.csv'))
        t = d['t_gz']
        t_desc = min([x for x in (oz.get('t_validate'), oz.get('t_commit')) if x is not None],
                     default=None)
        if t_desc is None:
            print(f'{os.path.basename(ep)}: alcalma durumu yok, atlandi')
            continue
        below = (t > t_desc) & (d['h_gercek_zemin'] < TEMAS_ESIGI_M)
        new = {}
        if below.any():
            i = int(np.argmax(below))
            tt = float(t[i])
            win = (t >= tt - 0.3) & (t <= tt)
            new['t_temas_gercek'] = tt
            new['temas_dikey_hiz_gercek_hesap_mps'] = float(np.nanmax(d['vz_gercek_hesap'][win]))
            gc = rising(t, d['ground_contact'], t_desc)
            new['t_px4_ground_contact'] = gc
            new['ground_contact_gecikmesi_s'] = (gc - tt) if gc else None
            tl = oz.get('t_px4_landed')
            new['landed_gecikmesi_s'] = (tl - tt) if tl else None
            yaml_path = None
            kosul = os.path.join(ep, 'kosul.yaml')
            if os.path.exists(kosul):
                for line in open(kosul):
                    if line.startswith('dunya_yaml:'):
                        yaml_path = line.split(':', 1)[1].strip()
            if yaml_path and 'x_gercek' in d:
                dw = dunya_mod.Dunya(yaml_path)
                new['temas_yeri_uygun'] = dw.hedefte_mi(float(d['x_gercek'][i]), float(d['y_gercek'][i]))
        onceki = {k: oz.get(k) for k in new}
        if all(onceki[k] == new[k] for k in new):
            print(f'{os.path.basename(ep)}: degisiklik yok')
            continue
        oz.setdefault('onceki', {}).update(onceki)
        oz.update(new)
        oz['basarili'] = bool(oz.get('t_px4_landed') is not None and not oz.get('kor_inis')
                              and bool(oz.get('temas_yeri_uygun')))
        oz['ozet_yenilendi'] = 'ozet_yenile.py: temas capasi min(t_validate, t_commit)'
        json.dump(oz, open(p, 'w'), indent=1, ensure_ascii=False)
        v = new.get('temas_dikey_hiz_gercek_hesap_mps')
        print(f"{os.path.basename(ep)}: temas t={new.get('t_temas_gercek')}, "
              f"hiz {v if v is None else round(v, 2)} m/s, "
              f"yer uygun {new.get('temas_yeri_uygun')}, basarili {oz['basarili']}")


if __name__ == '__main__':
    main()
