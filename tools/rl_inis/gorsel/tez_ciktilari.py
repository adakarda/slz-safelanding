"""Tez ciktilari: ogrenme egrileri, sonuc tablosu, sure dagilimi, basari-sure grafigi, AirSim tablosu.
Hepsi kosu gunluklerinden; yeni sonuc geldikce yeniden calistirilir. Sayilar olculen (val_b32, 320 deneme / kosu,
30 s, argmax); paper degerleri yalniz yan yana (kural farkli).

    bash ~/rl_inis/py.sh gorsel/tez_ciktilari.py [--cikti /mnt/c/Users/arda_/rl_gorsel/tez]
"""
import argparse
import csv
import glob
import json
import os
import statistics as st

import numpy as np

K = os.path.expanduser('~/rl_inis/kos')
G = os.path.expanduser('~/eland_veri/_gunlukler/airsim_faz3')
#: kol adi -> (dizin deseni, aciklama, egitim suresi s)
KOLLAR = {
    'B0': ('b_B0_s[0-9]', 'sora_v1', 90), 'B1': ('b_B1_s[0-9]', 'zemin_v1', 90),
    'B2': ('b_B2_s[0-9]', 'zemin_v1 + aynalama', 90), 'C1': ('c_C1_s[0-9]', 'zemin_v2', 90),
    'D1': ('d_D1_s[0-9]', 'zemin_v1, egitimde 30 s', 30), 'E1': ('e_E1_s[0-9]', 'D1 + kayarken alcal', 30),
    'F1': ('f_F1_s[0-9]', 'zemin_v3, egitimde 30 s', 30),
}
PAPER = (87.6, 11.8)


def olc(yol, yontem):
    rs = [r for r in csv.DictReader(open(yol)) if r['method'] == yontem]
    if not rs:
        return None
    n = len(rs)
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return dict(B=100 * len(ok) / n, T=st.mean(ok) if ok else float('nan'), sureler=ok,
                U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / n,
                TO=100 * sum(r['outcome'] == 'timeout' for r in rs) / n,
                Y=100 * sum(r['soft'] == '1' for r in rs) / n)


def kosular(desen):
    return sorted(d for d in glob.glob(os.path.join(K, desen)) if os.path.exists(os.path.join(d, 'eval_val.csv')))


def ms(v):
    v = [x for x in v if x == x]
    if not v:
        return '-'
    return f'{st.mean(v):.1f} ± {st.stdev(v):.1f}' if len(v) > 1 else f'{v[0]:.1f}'


def wilson(k, n, z=1.96):
    """95 % Wilson interval of a pooled success rate, in %."""
    if n == 0:
        return float('nan'), float('nan')
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return 100 * (c - h), 100 * (c + h)


def tum_kollar():
    """(kol, aciklama, [val_b32 csv per seed]): the pre-registered arms, then the screening's Tur 3 configs and
    the observation round's variant (amendments 15, 16) once they exist."""
    out = []
    for kol, (desen, ac, _) in KOLLAR.items():
        ds = kosular(desen)
        if ds:
            out.append((kol, ac, [f'{d}/eval_val.csv' for d in ds]))
    a = os.path.join(K, 'arama')
    for t2 in sorted(glob.glob(f'{a}/t2_*/eval_val_b32_10.csv')):
        ad = os.path.basename(os.path.dirname(t2))[3:]
        cs = [t2] + [p for p in (f'{a}/t3_{ad}_s{t}/eval_val_b32_10.csv' for t in (1, 2)) if os.path.exists(p)]
        out.append((f'T:{ad.split("_")[0]}', f'tarama {ad}', cs))
    g = os.path.expanduser('~/rl_inis/arama/gozlem/gozlem_sonuc.json')
    if os.path.exists(g):
        s = json.load(open(g))
        cs = [f'{d}/eval_val_b32_10.csv' for d in s['dizinler'] if os.path.exists(f'{d}/eval_val_b32_10.csv')]
        if cs:
            out.append((f'G:{s["cesit"].split("_")[0]}', f'gözlem {s["cesit"]} (taban {s["taban"]})', cs))
    return out


def tablo(cikti):
    satir = ['| Kol | Ayar | Tohum | RL başarı | RL+kalkan başarı | RL+kalkan %95 GA (havuz) | RL güvensiz | RL süre doldu | Çim | '
             'Başarılı iniş süresi (RL+kalkan, s) |',
             '|---|---|---|---|---|---|---|---|---|---|']
    csv_satir = [['kol', 'csv', 'rl_basari', 'kalkan_basari', 'rl_guvensiz', 'rl_sure_doldu', 'cim', 'kalkan_sure_s']]
    for kol, ac, cs in tum_kollar():
        r = [olc(c, 'rl') for c in cs]
        k = [olc(c, 'rl_kalkan') for c in cs]
        n = 320 * len(cs)
        lo, hi = wilson(round(sum(x['B'] for x in k) * 3.2), n)
        satir.append(f'| {kol} | {ac} | {len(cs)} | {ms([x["B"] for x in r])} | {ms([x["B"] for x in k])} | {lo:.1f}–{hi:.1f} | '
                     f'{ms([x["U"] for x in r])} | {ms([x["TO"] for x in r])} | {ms([x["Y"] for x in r])} | {ms([x["T"] for x in k])} |')
        for c, a_, b in zip(cs, r, k):
            csv_satir.append([kol, c, f'{a_["B"]:.1f}', f'{b["B"]:.1f}', f'{a_["U"]:.1f}', f'{a_["TO"]:.1f}', f'{a_["Y"]:.1f}',
                              f'{b["T"]:.1f}'])
    ref = kosular('b_B1_s0')[0] + '/eval_val.csv'
    for y, ad in (('duz_inis', 'düz alçalma'), ('duz_kalkan', 'düz alçalma + kalkan'), ('kanal', 'kanal pilotu'),
                  ('gorus_kahini', 'görüş kâhini (tavan)')):
        m = olc(ref, y)
        if m:
            satir.append(f'| — | {ad} | — | {m["B"]:.1f} | — | — | {m["U"]:.1f} | {m["TO"]:.1f} | {m["Y"]:.1f} | {m["T"]:.1f} |')
    satir.append(f'| paper | Bartolomei 2022 (kural farklı) | 1 | {PAPER[0]} | — | — | — | — | — | {PAPER[1]} |')
    open(f'{cikti}/sonuc_tablosu.md', 'w').write('\n'.join(satir) + '\n')
    with open(f'{cikti}/sonuc_tablosu.csv', 'w', newline='') as f:
        csv.writer(f).writerows(csv_satir)
    print('\n'.join(satir))


def egriler(cikti, plt):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    izgara = np.linspace(50_000, 1_000_000, 96)
    for kol, (desen, ac, sure) in KOLLAR.items():
        ys_b, ys_r = [], []
        for d in sorted(glob.glob(os.path.join(K, desen))):
            rows = []
            for f in glob.glob(os.path.join(d, 'monitor_[0-9]*.monitor.csv')):
                rows += list(csv.DictReader(l for l in open(f) if not l.startswith('#')))
            if len(rows) < 400:
                continue
            rows.sort(key=lambda r: float(r['t']))
            adim = np.cumsum([int(r['l']) for r in rows])
            ok = np.convolve([r['zemin_success'] == 'True' for r in rows], np.ones(300) / 300, mode='valid')
            od = np.convolve([float(r['r']) for r in rows], np.ones(300) / 300, mode='valid')
            a = adim[299:]
            if a[-1] < 900_000:
                continue
            ys_b.append(np.interp(izgara, a, 100 * ok))
            ys_r.append(np.interp(izgara, a, od))
        if not ys_b:
            continue
        for x, ys in ((ax[0], ys_b), (ax[1], ys_r)):
            m, s = np.mean(ys, 0), np.std(ys, 0)
            x.plot(izgara, m, label=f'{kol} ({ac}, {len(ys)} tohum)', ls='--' if sure == 30 else '-')
            x.fill_between(izgara, m - s, m + s, alpha=0.15)
    ax[0].set(xlabel='adım', ylabel='eğitimde zemin başarısı (%)', title='Eğitimde başarı (300 bölüm ort., gölge ±1σ)')
    ax[1].set(xlabel='adım', ylabel='bölüm ödülü', title='Eğitim ödülü (ödül ayarları farklı: yalnız kol içi)')
    for x in ax:
        x.grid(alpha=0.3)
    ax[0].legend(fontsize=7)
    fig.text(0.01, 0.01, 'kesik çizgi: eğitimde 30 s sınır (başarı oranları 90 s kollarla doğrudan kıyaslanmaz)', fontsize=7)
    fig.tight_layout()
    fig.savefig(f'{cikti}/ogrenme_egrileri.png', dpi=140)


def sure_ve_basari(cikti, plt):
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    kutular, adlar = [], []
    for kol, ac, cs in tum_kollar():
        sureler = sum((olc(c, 'rl_kalkan')['sureler'] for c in cs), [])
        if sureler:
            kutular.append(sureler)
            adlar.append(kol)
        for t, c in enumerate(cs):
            k = olc(c, 'rl_kalkan')
            ax[1].scatter(k['T'], k['B'], s=28, marker='s' if ':' in kol else 'o')
            ax[1].annotate(f'{kol}-{t}', (k['T'], k['B']), fontsize=6, xytext=(3, 3), textcoords='offset points')
    ax[0].boxplot(kutular, tick_labels=adlar, showfliers=False)
    ax[0].tick_params(axis='x', labelrotation=45, labelsize=7)
    ax[0].axhline(PAPER[1], color='tab:red', ls='--', lw=1, label='paper RL 11.8 s')
    ax[0].axhline(10.5, color='gray', ls=':', lw=1, label='bizde düz alçalma 10.5 s')
    ax[0].set(ylabel='başarılı iniş süresi (s), RL + kalkan', title='İniş süresi dağılımı')
    ax[0].legend(fontsize=7)
    ax[1].scatter(*PAPER[::-1], marker='*', s=150, color='tab:red')
    ax[1].annotate('paper (kural farklı)', PAPER[::-1], fontsize=7, xytext=(4, -10), textcoords='offset points')
    ax[1].set(xlabel='başarılı iniş süresi (s)', ylabel='zemin başarısı (%), RL + kalkan',
              title='Başarı ile hız (sağ alt değil, sol üst iyi)')
    ax[1].invert_xaxis()
    for x in ax:
        x.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(f'{cikti}/sure_ve_basari.png', dpi=140)


def airsim(cikti):
    satir = ['| Kol | İndi | Çim | Sert | Yol | Zemin kuralı | SORA 3 m | Süre medyan (s) |', '|---|---|---|---|---|---|---|---|']
    for f in sorted(glob.glob(f'{G}/*.jsonl.harita.jsonl')):
        rs = [json.loads(x) for x in open(f) if x.strip()]
        indi = [r for r in rs if 'harita_sinif' in r]
        s = [r['sure_s'] for r in indi if 'sure_s' in r]
        ad = os.path.basename(f).split('.')[0]
        satir.append(f'| {ad} | {len(indi)}/{len(rs)} | {sum(r["harita_sinif"] == 0 and r["zemin_uygun"] for r in indi)} | '
                     f'{sum(r["harita_sinif"] == 1 and r["zemin_uygun"] for r in indi)} | {sum(r["harita_ad"] == "yol" for r in indi)} | '
                     f'{sum(r["zemin_uygun"] for r in indi)} | {sum(r["sora_uygun"] for r in indi)} | {st.median(s) if s else "-"} |')
    open(f'{cikti}/airsim_tablosu.md', 'w').write('\n'.join(satir) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cikti', default='/mnt/c/Users/arda_/rl_gorsel/tez')
    a = ap.parse_args()
    os.makedirs(a.cikti, exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    tablo(a.cikti)
    egriler(a.cikti, plt)
    sure_ve_basari(a.cikti, plt)
    airsim(a.cikti)
    print('cikti:', a.cikti)


if __name__ == '__main__':
    main()
