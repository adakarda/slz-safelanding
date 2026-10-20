"""Duzeltme 16: gozlem turu (risk hafizasi, hedef noktasi, kademeli risk). docs/onkayit/rl_f0_onkayit.md.

Taban: taramanin Tur 3'unde ortalama skoru en yuksek ayar (H15 kabul etsin etmesin; bilinen en iyi aday).
Tabanin kosulari yeniden kosulmaz: Tur 1 (400k, val_b64 x 5), Tur 2 (1M, val_b64 x 10), Tur 3 (3 tohum, val_b32).

  G-A  4 cesit, tohum 0, 400k, val_b64 x 5:  +hafiza | +hedef | +risk | +risk,hedef,hafiza
  G-B  G-A'da skoru en yuksek 2 cesit: ayni kosu 1M'ye (--resume), val_b64 x 10
  G-C  G-B'nin en iyisi: tohum 1 ve 2 sifirdan 1M; uc tohum val_b32 x 10 (tam). Karar H16 (gozlem_karar.py).

Skor ve yer kurallari taramayla ayni (arama.py). Tarama bitmeden baslamaz.

    bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/arama/gozlem_tur.py'
"""
import glob
import json
import os
import statistics as st
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arama  # noqa: E402

H = os.path.expanduser('~')
AR = f'{H}/rl_inis/arama'
arama.A = f'{H}/rl_inis/arama/gozlem'
arama.K = f'{H}/rl_inis/kos/gozlem'
arama.EN_COK = 1    # every run here has --kanallar (~8.5 GB at peak): one at a time (yurutme notu 2026-10-20)
os.makedirs(arama.A, exist_ok=True)
os.makedirs(arama.K, exist_ok=True)
CESIT = [('g1_hafiza', 'hafiza'), ('g2_hedef', 'hedef'), ('g3_risk', 'risk'), ('g4_hepsi', 'risk,hedef,hafiza')]


def taban():
    """The Tur 3 config with the highest mean S on val_b32 (3 seeds), and its args."""
    kos = f'{H}/rl_inis/kos/arama'
    ayar = {}
    for yol in glob.glob(f'{kos}/t2_*/eval_val_b32_10.csv') + glob.glob(f'{kos}/t3_*_s[12]/eval_val_b32_10.csv'):
        d = os.path.basename(os.path.dirname(yol))
        ad = d[3:] if d.startswith('t2_') else d[3:].rsplit('_s', 1)[0]
        ayar.setdefault(ad, []).append(arama.olc(yol)['S'])
    tam = {ad: st.mean(v) for ad, v in ayar.items() if len(v) == 3}
    ad = max(tam, key=tam.get)
    konf = {c['ad']: c['args'] for c in json.load(open(f'{AR}/konfig_t1.json'))}
    return ad, konf[ad], tam[ad]


def main():
    def bitti(log, ifade):
        return os.path.exists(log) and ifade in open(log).read()
    # amendment 19: B2-s0's fine-tuning runs between the search and this round
    while not (bitti(f'{AR}/arama.log', 'arama bitti') and bitti(f'{AR}/b2hiz/arama.log', 'b2hiz bitti')):
        time.sleep(300)
    ad, args, s = taban()
    arama.log(f'gozlem turu basladi; taban {ad} (Tur 3 ortalama S {s:.1f}): {" ".join(args)}')
    tA = [arama.Is('G-A', c, [*args, '--kanallar', k], 0, f'{arama.K}/a_{c}', stop_at=400_000) for c, k in CESIT]
    arama.tur_kos(tA)
    sira = sorted(tA, key=lambda j: -j.sonuc['S'])
    arama.log('G-A bitti; sira: ' + ', '.join(f'{j.ad} {j.sonuc["S"]:.1f}' for j in sira))
    tB = [arama.Is('G-B', j.ad, j.args, 0, f'{arama.K}/b_{j.ad}', resume=f'{j.out}/model.zip',
                   degerlendir=('val_b64', 10)) for j in sira[:2]]
    arama.tur_kos(tB)
    en = max(tB, key=lambda j: j.sonuc['S'])
    arama.log(f'G-B bitti; en iyi {en.ad} S {en.sonuc["S"]:.1f}')
    tC = [arama.Is('G-C', en.ad, en.args, 0, en.out, degerlendir=('val_b32', 10), tam=True)]
    tC += [arama.Is('G-C', en.ad, en.args, t, f'{arama.K}/c_{en.ad}_s{t}', degerlendir=('val_b32', 10), tam=True)
           for t in (1, 2)]
    arama.tur_kos(tC)
    json.dump({'taban': ad, 'taban_args': args, 'cesit': en.ad, 'cesit_args': en.args,
               'dizinler': [j.out for j in tC]}, open(f'{arama.A}/gozlem_sonuc.json', 'w'), indent=1)
    print(arama.sh(f'python3 {AR}/gozlem_karar.py'), flush=True)
    arama.log('gozlem bitti')


if __name__ == '__main__':
    sys.exit(main())
