"""AirSim kollarinin .harita.jsonl dosyalarindan ozet: indi, cim (zemin uygun), sert, yol, zemin uygun, SORA, temas.

    python3 yumusak_say.py A.jsonl.harita.jsonl [B.jsonl.harita.jsonl ...]
"""
import collections
import json
import os
import sys

for p in sys.argv[1:]:
    rs = [json.loads(x) for x in open(p) if x.strip()]
    indi = [r for r in rs if 'harita_sinif' in r]
    ad = collections.Counter(r['harita_ad'] for r in indi)
    cim = sum(r['zemin_uygun'] and r['harita_sinif'] == 0 for r in indi)
    sert = sum(r['zemin_uygun'] and r['harita_sinif'] == 1 for r in indi)
    print(f'{os.path.basename(p).split(".")[0]:22s} kosu {len(rs):2d} indi {len(indi):2d}  cim {cim:2d}  sert {sert:2d}  '
          f'zemin {sum(r["zemin_uygun"] for r in indi):2d}  SORA {sum(r["sora_uygun"] for r in indi):2d}  siniflar {dict(ad)}')
