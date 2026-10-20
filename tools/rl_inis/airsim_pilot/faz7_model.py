"""Faz 7'nin RL modeli (on kayitli kural, airsim_faz7_onkayit.md): once E (Duzeltme 13), sonra D (Duzeltme 12)
benimsendiyse onun tohumlari icinden val_b32'de RL + kalkan zemin basarisi en yuksek olan; hicbiri benimsenmediyse B2-s0.

    python3 faz7_model.py      -> "<model.zip yolu> <aciklama>"
"""
import csv
import os
import subprocess

K = os.path.expanduser('~/rl_inis/kos')


def benimsendi(betik):
    out = subprocess.run(['python3', os.path.expanduser(f'~/rl_inis/{betik}')], capture_output=True, text=True).stdout
    return any(s.startswith('KARAR:') and 'benimsenir' in s for s in out.splitlines())


def en_iyi(onek):
    def puan(t):
        rs = [r for r in csv.DictReader(open(os.path.join(K, f'{onek}_s{t}', 'eval_val.csv'))) if r['method'] == 'rl_kalkan']
        return sum(r['zemin_success'] == '1' for r in rs) / len(rs)
    t = max((0, 1, 2), key=puan)
    return os.path.join(K, f'{onek}_s{t}', 'model.zip'), f'{onek}_s{t} (RL + kalkan val {100 * puan(t):.1f} %)'


def arama_kazanani():
    """Amendment 15 (Faz 7 amendment 2): the screening's winner, if H15 named it the new best."""
    out = subprocess.run(['python3', os.path.expanduser('~/rl_inis/arama/kararla.py')], capture_output=True, text=True).stdout
    for s in out.splitlines():
        if s.startswith('KARAR:') and 'yeni en iyi ayar' in s:
            ayar = s.split()[1]
            yollar = [os.path.join(K, 'arama', f't2_{ayar}')] + [os.path.join(K, 'arama', f't3_{ayar}_s{t}') for t in (1, 2)]

            def puan(d):
                rs = [r for r in csv.DictReader(open(os.path.join(d, 'eval_val_b32_10.csv'))) if r['method'] == 'rl_kalkan']
                return sum(r['zemin_success'] == '1' for r in rs) / len(rs)
            d = max(yollar, key=puan)
            return os.path.join(d, 'model.zip'), f'{os.path.basename(d)} (arama kazanani; RL + kalkan val {100 * puan(d):.1f} %)'
    return None


def gozlem_kazanani():
    """Amendment 16: the observation round's variant, if H16 adopted it (it builds on the search's best)."""
    karar = os.path.expanduser('~/rl_inis/arama/gozlem_karar.py')
    sonuc = os.path.expanduser('~/rl_inis/arama/gozlem/gozlem_sonuc.json')
    if not (os.path.exists(karar) and os.path.exists(sonuc)):
        return None
    out = subprocess.run(['python3', karar], capture_output=True, text=True).stdout
    if not any(s.startswith('KARAR:') and 'benimsenir' in s for s in out.splitlines()):
        return None
    import json

    def puan(d):
        rs = [r for r in csv.DictReader(open(os.path.join(d, 'eval_val_b32_10.csv'))) if r['method'] == 'rl_kalkan']
        return sum(r['zemin_success'] == '1' for r in rs) / len(rs)
    d = max(json.load(open(sonuc))['dizinler'], key=puan)
    return os.path.join(d, 'model.zip'), f'{os.path.basename(d)} (gozlem turu kazanani; RL + kalkan val {100 * puan(d):.1f} %)'


def birlesim_kazanani():
    """Amendment 18: the combination round's final candidate: its 2M seeds if H18b chose 2M, else its variant if H18
    adopted it, else its base (the best before it). The seed with the highest RL + kalkan on val_b32."""
    karar = os.path.expanduser('~/rl_inis/arama/birlesim_karar.py')
    sonuc = os.path.expanduser('~/rl_inis/arama/birlesim/birlesim_sonuc.json')
    if not (os.path.exists(karar) and os.path.exists(sonuc)):
        return None
    import json
    s = json.load(open(sonuc))
    out = subprocess.run(['python3', karar], capture_output=True, text=True).stdout.splitlines()
    if any('KARAR2M: 2M kullanilir' in x for x in out):
        dz, neden = s['uzun_dizinler'], 'birlesim turu, 2M'
    elif any(x.startswith('KARAR:') and 'benimsenir' in x for x in out):
        dz, neden = s['dizinler'], f'birlesim turu cesidi {s["cesit"]}'
    else:
        dz, neden = s['taban_dizinler'], f'birlesim turunun tabani {s["taban"]}'

    def puan(d):
        rs = [r for r in csv.DictReader(open(os.path.join(d, 'eval_val_b32_10.csv'))) if r['method'] == 'rl_kalkan']
        return sum(r['zemin_success'] == '1' for r in rs) / len(rs)
    d = max(dz, key=puan)
    return os.path.join(d, 'model.zip'), f'{os.path.basename(d)} ({neden}; RL + kalkan val {100 * puan(d):.1f} %)'


kazanan = birlesim_kazanani() or gozlem_kazanani() or (
    arama_kazanani() if os.path.exists(os.path.expanduser('~/rl_inis/arama/kararla.py')) else None)
if kazanan:
    yol, ad = kazanan
elif benimsendi('h14_karar.py'):          # amendment 14, written before Faz 7 ran: F first
    yol, ad = en_iyi('f_F1')
elif benimsendi('h13_karar.py'):
    yol, ad = en_iyi('e_E1')
elif benimsendi('h12_karar.py'):
    yol, ad = en_iyi('d_D1')
else:
    yol, ad = os.path.join(K, 'b_B2_s0', 'model.zip'), 'b_B2_s0 (D ve E benimsenmedi)'
print(yol, ad)
