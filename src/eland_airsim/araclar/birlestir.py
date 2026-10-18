"""Bir kolun ana batch sonucunu, eksik baslangiclarin yeniden kosusuyla birlestir.

    python3 birlestir.py ANA.jsonl EK.jsonl CIKTI.jsonl

Ana batch'te "indi" olmayan bir baslangic EK'te varsa EK'teki sonuc alinir; deneme sayilari toplanir ve
"not" alanina ilk sonuc yazilir. Eslesme (x, y) baslangic koordinatiyla.
"""
import json
import os
import sys

ana = [json.loads(x) for x in open(sys.argv[1]) if x.strip()]
ek = {(r['x'], r['y']): r for r in (json.loads(x) for x in open(sys.argv[2]) if x.strip())}
out = []
for r in ana:
    if r.get('sonuc') != 'indi' and (r['x'], r['y']) in ek:
        e = dict(ek[(r['x'], r['y'])])
        e['kosu'] = r['kosu']
        e['deneme'] = r.get('deneme', 1) + e.get('deneme', 1)
        e['coken'] = r.get('coken', 0) + e.get('coken', 0)
        e['not'] = f"ilk deneme {r.get('sonuc')}; yeniden kosuldu"
        r = e
    out.append(r)
os.makedirs(os.path.dirname(os.path.abspath(sys.argv[3])), exist_ok=True)
with open(sys.argv[3], 'w') as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(len(out), [r.get('sonuc') for r in out])
