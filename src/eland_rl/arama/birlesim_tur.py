"""Duzeltme 18: birlesim turu. docs/onkayit/rl_f0_onkayit.md. Gozlem turu bitince baslar.

Taban (sonuctan once sabit kural): gozlem turu cesidi benimsendiyse (H16) o cesit, degilse taramanin Tur 3'unde
ortalama S'si en yuksek ayar. Tabanin kosulari yeniden kosulmaz (400k val_b64 x 5, 1M val_b64 x 10, 3 tohum val_b32).

Cesitler (tabanin argumanlari uzerine):
  k1_hiz      + adim cezasi -0.5 ve alcal +1 (c23'un hiz odulu)
  k2_odul     odul degisir: taban zemin_v3 ise zemin_v1, zemin_v1 ise zemin_v3
  k3_impala   + IMPALA govdesi (Arda'nin onayiyla, K79)
  k4_90s_hiz  egitimde 90 s (--max-t kalkar) + hiz odulu
  k5_c13_kanal  (Duzeltme 20) c13'un tarifi (zemin_v3, 30 s, --diag, kalkan egitimde) + tabanin --kanallar'i;
               yalniz taban bir gozlem kanali iceriyorsa (yoksa k5 = c13, taramada olculdu)
  K-A  4 cesit, tohum 0, 400k, val_b64 x 5 | K-B  en iyi 2, 1M, val_b64 x 10 | K-C  en iyisi 3 tohum, val_b32 x 10
  K-D  H18 kazanani (yoksa taban) 3 tohumu 2M'ye uzatilir (--resume, --steps 2000000), val_b32 x 10; H18b.

    bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/arama/birlesim_tur.py'
"""
import glob
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arama  # noqa: E402

H = os.path.expanduser('~')
AR = f'{H}/rl_inis/arama'
arama.A = f'{AR}/birlesim'
arama.K = f'{H}/rl_inis/kos/birlesim'
os.makedirs(arama.A, exist_ok=True)
os.makedirs(arama.K, exist_ok=True)
HIZ = {'r_step': -0.5, 'a_descend': 1.0}
C13 = ['--reward', 'zemin_v3', '--max-t', '30', '--diag', '--shield-train-m', '10']   # amendment 20


def taban():
    """(ad, args, csv_400k_b64_5, csv_1M_b64_10, [3 x val_b32 csv], [3 seed run dirs])."""
    karar = subprocess.run(['python3', f'{AR}/gozlem_karar.py'], capture_output=True, text=True).stdout
    g = f'{AR}/gozlem/gozlem_sonuc.json'
    if os.path.exists(g) and any(s.startswith('KARAR:') and 'benimsenir' in s for s in karar.splitlines()):
        s = json.load(open(g))
        gk = f'{H}/rl_inis/kos/gozlem'
        dz = s['dizinler']
        return (s['cesit'], s['cesit_args'], f'{gk}/a_{s["cesit"]}/eval_val_b64_5.csv',
                f'{dz[0]}/eval_val_b64_10.csv', [f'{d}/eval_val_b32_10.csv' for d in dz], dz)
    k = f'{H}/rl_inis/kos/arama'
    puan = {}
    for t2 in glob.glob(f'{k}/t2_*/eval_val_b32_10.csv'):
        ad = os.path.basename(os.path.dirname(t2))[3:]
        cs = [t2] + [f'{k}/t3_{ad}_s{t}/eval_val_b32_10.csv' for t in (1, 2)]
        if all(os.path.exists(c) for c in cs):
            puan[ad] = st.mean(arama.olc(c)['S'] for c in cs)
    ad = max(puan, key=puan.get)
    konf = {c['ad']: c['args'] for c in json.load(open(f'{AR}/konfig_t1.json'))}
    dz = [f'{k}/t2_{ad}', f'{k}/t3_{ad}_s1', f'{k}/t3_{ad}_s2']
    return (ad, konf[ad], f'{k}/t1_{ad}/eval_val_b64_5.csv', f'{k}/t2_{ad}/eval_val_b64_10.csv',
            [f'{d}/eval_val_b32_10.csv' for d in dz], dz)


def ayarla(args, cikar=(), ekle=(), env=None, odul=None):
    """Copy of args without the options in cikar (with their values), then ekle; env merges into --env-json."""
    out, i = [], 0
    tek = {'--diag', '--shard', '--binary', '--mirror'}
    while i < len(args):
        a = args[i]
        deger = 0 if a in tek else 1
        if a in cikar:
            i += 1 + deger
            continue
        if a == '--reward' and odul:
            out += [a, odul]
        elif a == '--env-json' and env is not None:
            out += [a, json.dumps({**json.loads(args[i + 1]), **env})]
            env = None
        else:
            out += args[i:i + 1 + deger]
        i += 1 + deger
    if env is not None:
        out += ['--env-json', json.dumps(env)]
    return out + list(ekle)


def cesitler(args):
    odul = arama.secenek(args, '--reward') or 'zemin_v1'
    aday = [('k1_hiz', ayarla(args, env=HIZ)),
            ('k2_odul', ayarla(args, odul='zemin_v1' if odul == 'zemin_v3' else 'zemin_v3')),
            ('k3_impala', ayarla(args, cikar=('--encoder',), ekle=('--encoder', 'impala'))),
            ('k4_90s_hiz', ayarla(args, cikar=('--max-t',), env=HIZ))]
    kanal = arama.secenek(args, '--kanallar')
    if kanal:   # amendment 20: the fastest recipe of the search (c13) with the base's observation channels
        aday.append(('k5_c13_kanal', [*C13, '--kanallar', kanal]))
    out, gorulen = [], [args]                 # a variant that changes nothing (base already has it) is dropped
    for c, a in aday:
        if a not in gorulen:
            out.append((c, a))
            gorulen.append(a)
    return out


def main():
    while not (os.path.exists(f'{AR}/gozlem/arama.log') and 'gozlem bitti' in open(f'{AR}/gozlem/arama.log').read()):
        time.sleep(300)
    ad, args, cA, cB, cC, dz = taban()
    if '--kanallar' in args:
        arama.EN_COK = 1    # observation channels: ~8.5 GB per run at peak, one at a time (yurutme notu 2026-10-20)
    sA, sB = arama.olc(cA)['S'], arama.olc(cB)['S']
    arama.log(f'birlesim turu basladi; taban {ad} ({" ".join(args)}); taban S: 400k {sA:.1f}, 1M {sB:.1f}')
    tA = [arama.Is('K-A', c, a, 0, f'{arama.K}/a_{c}', stop_at=400_000) for c, a in cesitler(args)]
    arama.tur_kos(tA)
    sira = sorted(tA, key=lambda j: -j.sonuc['S'])
    arama.log('K-A bitti; sira: ' + ', '.join(f'{j.ad} {j.sonuc["S"]:.1f}' for j in sira) + f' (taban {sA:.1f})')
    tB = [arama.Is('K-B', j.ad, j.args, 0, f'{arama.K}/b_{j.ad}', resume=f'{j.out}/model.zip',
                   degerlendir=('val_b64', 10)) for j in sira[:2]]
    arama.tur_kos(tB)
    en = max(tB, key=lambda j: j.sonuc['S'])
    arama.log(f'K-B bitti; en iyi {en.ad} S {en.sonuc["S"]:.1f} (taban {sB:.1f})')
    tC = [arama.Is('K-C', en.ad, en.args, 0, en.out, degerlendir=('val_b32', 10), tam=True)]
    tC += [arama.Is('K-C', en.ad, en.args, t, f'{arama.K}/c_{en.ad}_s{t}', degerlendir=('val_b32', 10), tam=True)
           for t in (1, 2)]
    arama.tur_kos(tC)
    sonuc = {'taban': ad, 'taban_args': args, 'taban_dizinler': dz, 'taban_csv': cC,
             'cesit': en.ad, 'cesit_args': en.args, 'dizinler': [j.out for j in tC]}
    json.dump(sonuc, open(f'{arama.A}/birlesim_sonuc.json', 'w'), indent=1)
    karar = arama.sh(f'python3 {AR}/birlesim_karar.py')
    print(karar, flush=True)
    kazanan = (en.args, [j.out for j in tC]) if 'KARAR: ' + en.ad + ' benimsenir' in karar else (args, dz)
    # K-D: the final candidate's three seeds carried on to 2M (fresh directories; the 1M runs stay as they are)
    tD = []
    for t, d in enumerate(kazanan[1]):
        out = f'{arama.K}/d_2M_s{t}'
        tD.append(arama.Is('K-D', '2M', [*kazanan[0], '--steps', '2000000'], t, out, resume=f'{d}/model.zip',
                           degerlendir=('val_b32', 10), tam=True))
    arama.tur_kos(tD)
    sonuc.update(uzun_kaynak=kazanan[1], uzun_dizinler=[j.out for j in tD])
    json.dump(sonuc, open(f'{arama.A}/birlesim_sonuc.json', 'w'), indent=1)
    print(arama.sh(f'python3 {AR}/birlesim_karar.py'), flush=True)
    arama.log('birlesim bitti')


if __name__ == '__main__':
    sys.exit(main())
