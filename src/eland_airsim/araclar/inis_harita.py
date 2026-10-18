"""Inis noktalarini ortografik GT haritasinda degerlendir (olcum, sonradan; inis davranisina dokunmaz).

    ~/v3_test/venv/bin/python inis_harita.py HARITA.npz SONUC.jsonl [SONUC2.jsonl ...]

Her "indi" satiri icin dunya NED konumu = baslangic (x, y) + inis_ned (aracin kendi orijini, yaw 0),
haritadaki sinif (0..6, 7 = yol), en yakin tehlikeye (3,4,5,6) ve en yakin yol/agac (2,7) hucresine uzaklik.
SORA (dedektorun kurali): guvenli sinif ve tehlikeye >= 3 m. Zemin kurali (B deneyi): guvenli sinif ve
insan/araca (6,5) >= 2 m. Satirlara alan ekler ve yan dosya <jsonl>.harita.jsonl yazar.
"""
import json
import sys

import cv2
import numpy as np

AD = {0: 'cim', 1: 'sert', 2: 'agac', 3: 'yapi', 4: 'su', 5: 'arac', 6: 'insan', 7: 'yol', 255: 'bilinmeyen'}


def main():
    h = np.load(sys.argv[1])
    m, res, n_top, e_sol = h['sinif'], float(h['res']), float(h['n_top']), float(h['e_sol'])
    sinif = np.where(m == 255, 7, m)     # unknown is not landable either; treat like the road for distances
    d_haz = cv2.distanceTransform((~np.isin(m, [3, 4, 5, 6])).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res
    d_pv = cv2.distanceTransform((~np.isin(m, [5, 6])).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res
    d_yol = cv2.distanceTransform((~np.isin(m, [2, 7])).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) * res
    for path in sys.argv[2:]:
        rows = [json.loads(x) for x in open(path) if x.strip()]
        out = []
        for r in rows:
            if r.get('sonuc') == 'indi':
                n = r['x'] + r['inis_ned'][0]
                e = r['y'] + r['inis_ned'][1]
                i, j = int((n_top - n) / res), int((e - e_sol) / res)
                if 0 <= i < m.shape[0] and 0 <= j < m.shape[1]:
                    c = int(m[i, j])
                    r.update(harita_sinif=c, harita_ad=AD.get(c, '?'),
                             tehlikeye_m=round(float(d_haz[i, j]), 2), insan_araca_m=round(float(d_pv[i, j]), 2),
                             yol_agaca_m=round(float(d_yol[i, j]), 2),
                             sora_uygun=bool(c in (0, 1) and d_haz[i, j] >= 3.0),
                             zemin_uygun=bool(c in (0, 1) and d_pv[i, j] >= 2.0))
            out.append(r)
        with open(path + '.harita.jsonl', 'w') as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        indi = [r for r in out if 'harita_sinif' in r]
        print(f'{path}: {len(out)} kosu, {len(indi)} indi; harita sinifi '
              f'{[r["harita_ad"] for r in indi]}; SORA uygun {sum(r["sora_uygun"] for r in indi)}/{len(indi)}, '
              f'zemin uygun {sum(r["zemin_uygun"] for r in indi)}/{len(indi)}; tehlikeye m {[r["tehlikeye_m"] for r in indi]}')


if __name__ == '__main__':
    main()
