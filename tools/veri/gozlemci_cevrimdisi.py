#!/usr/bin/env python3
"""Replay the height observer over recorded episodes -- offline, OPEN LOOP.

    tools/veri/gozlemci_cevrimdisi.py ozet     # W5 windowed / not, W3, Asama 5
    tools/veri/gozlemci_cevrimdisi.py model    # 3a: rho = A/(4.216 h^2) vs record
    tools/veri/gozlemci_cevrimdisi.py nu0      # is nu ~ 0 at the first frame by construction?
    tools/veri/gozlemci_cevrimdisi.py loo      # Kalman sigmas: leave one episode / scenario out
    tools/veri/gozlemci_cevrimdisi.py sapma    # where the W3 bias comes from
    ... [--kok ~/eland_veri] [--rapor FILE.md]

Open loop: the estimate never changed the speed, and the speed never changed
the height. Nothing here measures a landing. ``v_temas_hesap`` only says what
the altitude law, clamp(0.35 h, 0.3, ceiling), would have commanded at
touchdown had it been fed this estimate.

Same estimator code as the live node: src/eland_mapping/eland_mapping/
gozlem_hesap.py. The replay steps on the 50 Hz grid of duzenli.csv, from the
first VALIDATE to the Gazebo touchdown; each mask frame arrives at its capture
stamp (plus --gecikme) and is compared with the estimate as it was at capture.
Truth is maske_olaylari.csv's h_kamera_gercek (camera height above the
surface below it).

W5 is always reported in two groups: "pencereli" -- at least 10 frames in
which the platform fits the view during the descent -- and "penceresiz". With
no such frame no image method can learn anything, and averaging the two would
pass that limit of the scenario off as a property of the estimator.
"""
import argparse
import csv
import glob
import itertools
import json
import math
import os
import sys

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'src', 'eland_mapping'))
from eland_mapping import gozlem_hesap as G  # noqa: E402
from eland_mapping.p_hesap import AYAK_IZI  # noqa: E402

#: Camera height above the mode's altitude zero (model origin + 0.10 m camera
#: mount, rest offset -0.013 m on W5), m. Measured; see the 'sapma' report.
KAMERA_OFSETI = 0.09
PENCERE_KARE = 10
ACIK_CEVRIM = '*Açık çevrim: tahmin hızı değiştirmedi, iniş sonucu ölçülmedi.*'


# ------------------------------------------------------------------ loading
def _oku(p, cols):
    with open(p) as f:
        r = csv.reader(f)
        hdr = next(r)
        ix = [hdr.index(c) if c in hdr else None for c in cols]
        rows = list(r)
    out = {}
    for c, i in zip(cols, ix):
        out[c] = np.array([float(x[i]) if i is not None and i < len(x) and x[i] not in ('', 'None', 'nan')
                           else np.nan for x in rows])
    return out


def _alan_gercek(ep):
    try:
        k = yaml.safe_load(open(os.path.join(ep, 'kosul.yaml')))
        w = yaml.safe_load(open(k['dunya_yaml']))
        for y in w.get('yuzeyler', []):
            if y.get('ad') == w.get('hedef') and y.get('alan_m2'):
                return float(y['alan_m2'])
    except Exception:  # noqa: BLE001 -- missing world yaml: no area truth
        pass
    return None


def yukle(ep):
    oz = json.load(open(os.path.join(ep, 'ep_ozet.json')))
    t0, t1 = oz.get('t_validate'), oz.get('t_temas_gercek')
    if t0 is None or t1 is None:
        return None
    m = _oku(os.path.join(ep, 'maske_olaylari.csv'),
             ('t_yakalama', 'rho', 'view_bounded', 'h_kamera_gercek', 'rho_bozuk', 'view_bounded_bozuk'))
    d = _oku(os.path.join(ep, 'duzenli.csv'),
             ('t_gz', 'h_ekf', 'vz_ekf', 'roll', 'pitch', 'h_gercek_hedef', 'vz_gercek_hesap'))
    k = _oku(os.path.join(ep, 'karar_olaylari.csv'), ('t_alma', 'gecerli', 'area_m2'))
    s = np.argsort(d['t_gz'])
    d = {c: v[s] for c, v in d.items()}
    d['egiklik'] = np.degrees(np.arccos(np.clip(np.cos(d['roll']) * np.cos(d['pitch']), -1, 1)))
    ok = (k['gecerli'] == 1) & (k['area_m2'] > 0)
    once = ok & (k['t_alma'] <= t0)
    a0 = k['area_m2'][once][-1] if once.any() else (k['area_m2'][ok][0] if ok.any() else np.nan)
    sm = (m['t_yakalama'] >= t0) & (m['t_yakalama'] <= t1)
    n_sinirli = int(((m['view_bounded'] == 1) & (m['rho'] > 0) & sm).sum())
    return dict(ep=ep, ad=os.path.basename(ep), oz=oz, t0=t0, t1=t1, m=m, d=d, a0=a0,
                a=_alan_gercek(ep), n_sinirli=n_sinirli)


def bolumler(kok, desen):
    out = []
    for ep in sorted(glob.glob(os.path.join(kok, desen))):
        try:
            b = yukle(ep)
        except (OSError, KeyError, StopIteration, ValueError):
            b = None
        if b is not None and np.isfinite(b['a0']):
            out.append(b)
    return out


# ------------------------------------------------------------------ replay
def kos(b, yap, gecikme=0.0, damga=True, rho_kol='rho', vb_kol='view_bounded',
        ilerletme='vz', ofset=KAMERA_OFSETI):
    """Run one estimator over one episode. yap() returns a fresh estimator."""
    m, d = b['m'], b['d']
    tg = d['t_gz']
    i0, i1 = np.searchsorted(tg, b['t0']), np.searchsorted(tg, b['t1'])
    if i1 - i0 < 10:
        return None
    e = yap()
    e.baslat(tg[i0], d['h_ekf'][i0] + ofset, b['a0'])
    ty = m['t_yakalama']
    ta = ty + gecikme
    sira = np.argsort(ta)
    ty, ta, rho, vb = ty[sira], ta[sira], m[rho_kol][sira], m[vb_kol][sira]
    j = np.searchsorted(ta, tg[i0])
    t_out, h_out, kul_t, kul_d = [], [], [], []
    nu_ilk = None
    hg_m = np.isfinite(m['h_kamera_gercek'])
    for i in range(i0, i1):
        if i > i0:
            if ilerletme == 'vz':
                vz = d['vz_ekf'][i - 1]
            else:  # the EKF height's own displacement
                vz = -(d['h_ekf'][i] - d['h_ekf'][i - 1]) / max(tg[i] - tg[i - 1], 1e-3)
            if np.isfinite(vz):  # a missing sample: the next step covers the gap
                e.ilerlet(tg[i], vz)
        while j < len(ta) and ta[j] <= tg[i]:
            r = rho[j]
            if np.isfinite(r):
                eg = float(np.interp(ty[j], tg, d['egiklik']))
                k = e.olcum(ty[j], float(r), bool(vb[j] == 1), eg, damga_kullan=damga)
                if k in (0, G.KAPI_AYKIRI) and nu_ilk is None:
                    nu_ilk = e.nu     # first frame the model applies to, used or not
                if k == 0:
                    kul_t.append(ty[j])
                    hgt = float(np.interp(ty[j], m['t_yakalama'][hg_m], m['h_kamera_gercek'][hg_m]))
                    kul_d.append(float(np.interp(ty[j], tg, d['vz_ekf'])) / max(hgt, 0.1))
            j += 1
        t_out.append(tg[i])
        h_out.append(e.h)
    return dict(t=np.array(t_out), h=np.array(h_out), e=e, kul_t=np.array(kul_t),
                kul_d=np.array(kul_d), alan=e.alan,
                nu_ilk=float('nan') if nu_ilk is None else nu_ilk)


def olc(b, r, ofset=KAMERA_OFSETI):
    if r is None:
        return None
    m = b['m']
    s = np.isfinite(m['h_kamera_gercek'])
    hg = np.interp(r['t'], m['t_yakalama'][s], m['h_kamera_gercek'][s])
    err = r['h'] - hg

    def at(hh):
        k = np.nonzero(hg <= hh)[0]
        return float(err[k[0]]) if len(k) else float('nan')

    band = (hg >= 2) & (hg <= 10)
    tavan = min(max(0.2 * math.sqrt(b['a0']), 0.3), 1.5)
    h_mod = r['h'][-1] - ofset
    return dict(e8=at(8), e5=at(5), e3=at(3), e2=at(2),
                rms=float(np.sqrt(np.mean(err[band] ** 2))) if band.any() else float('nan'),
                v_td=min(max(0.35 * h_mod, 0.3), tavan),
                kul=len(r['kul_t']),
                d_max=float(np.max(r['kul_d'])) if len(r['kul_d']) else float('nan'),
                alan_oran=r['alan'] / b['a'] if b['a'] else float('nan'))


def ozet_satir(ad, bs, yap, **kw):
    R = [o for o in (olc(b, kos(b, yap, **kw)) for b in bs) if o is not None]
    if not R:
        return f'| {ad} | — | — | — | — | — |'
    f = lambda k: np.array([x[k] for x in R], float)  # noqa: E731
    e2 = f('e2')
    return (f'| {ad} | {len(R)} | {np.nanmedian(e2):+.2f} ({np.nanmin(e2):+.2f}…{np.nanmax(e2):+.2f}) '
            f'| {np.nanmedian(f("rms")):.2f} | {np.nanmedian(f("v_td")):.2f} / {np.nanmax(f("v_td")):.2f} '
            f'| {np.nanmedian(f("kul")):.0f} |')


TABLO_BASLIK = ('| yöntem | bölüm | 2 m\'de hata, m: ortanca (en küçük…en büyük) | RMS 2–10 m | '
                'v_temas_hesap ortanca / en büyük | kullanılan kare |\n|---|---|---|---|---|---|')


def yapici(tur, **kw):
    if tur == 'sabit':
        return lambda: G.Sabit(kx=kw.get('kx', 2.0), kc=kw.get('kc', -2.0), kapilar=G.Kapilar())
    if tur == 'kalman':
        return lambda: G.Kalman(sigma_olcum=kw.get('so', 0.02), sigma_x0=kw.get('sx', 0.5),
                                sigma_c0=kw.get('sc', 0.7), kapilar=G.Kapilar())
    raise ValueError(tur)


def ekf_kos(b):
    d = b['d']
    tg = d['t_gz']
    i0, i1 = np.searchsorted(tg, b['t0']), np.searchsorted(tg, b['t1'])
    return dict(t=tg[i0:i1], h=d['h_ekf'][i0:i1] + KAMERA_OFSETI, kul_t=np.array([]),
                kul_d=np.array([]), alan=b['a0'], e=None)


# ------------------------------------------------------------------ commands
def cmd_ozet(a, out):
    w5 = bolumler(a.kok, 'k[1-3]*/veri_w5/*') + bolumler(a.kok, 'kol0/veri_w5/*')
    w3 = bolumler(a.kok, 'k[13]*/veri_w3/*') + bolumler(a.kok, 'kol0/veri_w3/*')
    gruplar = [('W5 pencereli', [b for b in w5 if b['n_sinirli'] >= PENCERE_KARE]),
               ('W5 penceresiz', [b for b in w5 if b['n_sinirli'] < PENCERE_KARE]),
               ('W3 düz', w3)]
    for ad, bs in gruplar:
        out(f'\n### {ad} ({len(bs)} bölüm)\n\n{ACIK_CEVRIM}\n\n{TABLO_BASLIK}')
        R = [olc(b, ekf_kos(b)) for b in bs]
        e2 = np.array([x['e2'] for x in R])
        v = np.array([x['v_td'] for x in R])
        out(f'| EKF (bugünkü girdi) | {len(R)} | {np.nanmedian(e2):+.2f} ({np.nanmin(e2):+.2f}…{np.nanmax(e2):+.2f}) '
            f'| — | {np.nanmedian(v):.2f} / {np.nanmax(v):.2f} | — |')
        out(ozet_satir('sabit 2/−2', bs, yapici('sabit')))
        out(ozet_satir('sabit 3.5/−5', bs, yapici('sabit', kx=3.5, kc=-5.0)))
        out(ozet_satir('kalman 0.02/0.5/0.7', bs, yapici('kalman')))
    # D against 2Kx + Kc on the frames that corrected the estimate
    out('\n### D = vz/h, kullanılan karelerde (gerçek h ile)\n\n' + ACIK_CEVRIM + '\n')
    out('| grup | kazanç | D en büyük | D %95 | 2Kx+Kc | aşan kare |\n|---|---|---|---|---|---|')
    for ad, bs in gruplar:
        for kx, kc in ((2.0, -2.0), (3.5, -5.0)):
            ds = np.concatenate([r['kul_d'] for r in (kos(b, yapici('sabit', kx=kx, kc=kc)) for b in bs)
                                 if r is not None and len(r['kul_d'])] or [np.array([np.nan])])
            sinir = 2 * kx + kc
            out(f'| {ad} | {kx}/{kc} | {np.nanmax(ds):.3f} | {np.nanpercentile(ds, 95):.3f} | {sinir:.1f} '
                f'| {int(np.sum(ds > sinir))} / {int(np.sum(np.isfinite(ds)))} |')
    # Asama 5, W3, recorded disturbed masks
    out(f'\n### Aşama 5 bozuk maskeler, W3, sabit 2/−2\n\n{ACIK_CEVRIM}\n\n{TABLO_BASLIK}')
    for tur in ('sinir2', 'cevir0.02', 'kayip0.05', 'tekrar2', 'gecikme0.2'):
        bs = bolumler(a.kok, f'a5_*/veri_w3/*_{tur}')
        out(ozet_satir(f'{tur} temiz ρ', bs, yapici('sabit')))
        kw = dict(rho_kol='rho_bozuk', vb_kol='view_bounded_bozuk')
        if tur.startswith('gecikme'):
            out(ozet_satir(f'{tur} bozuk ρ, damga kullanılır', bs, yapici('sabit'), gecikme=0.2, **kw))
            out(ozet_satir(f'{tur} bozuk ρ, damga yok sayılır', bs, yapici('sabit'), gecikme=0.2, damga=False, **kw))
        else:
            out(ozet_satir(f'{tur} bozuk ρ', bs, yapici('sabit'), **kw))


def cmd_model(a, out):
    duz = (bolumler(a.kok, 'k[13]*/veri_w[2-8]/*') + bolumler(a.kok, 'kol0/veri_w[2-8]/*'))
    duz = [b for b in duz if 'w5' not in b['ad']]
    w5 = bolumler(a.kok, 'k[13]*/veri_w5/*') + bolumler(a.kok, 'kol0/veri_w5/*')
    out('\n### 3a: ρ = A/(4.216·h²), kayıtlı temiz maske\n')
    oran = []
    for b in duz + w5:
        if not b['a']:
            continue
        m, d = b['m'], b['d']
        t = m['t_yakalama']
        eg = np.interp(t, d['t_gz'], d['egiklik'])
        s = ((t >= b['t0']) & (t <= b['t1']) & (m['view_bounded'] == 1) & (eg < 5)
             & (m['rho'] > 0.003) & (m['rho'] < 0.98) & (m['h_kamera_gercek'] > 0.3))
        if s.sum() >= 5:
            c = np.median(np.log(m['rho'][s]) + 2 * np.log(m['h_kamera_gercek'][s]))
            oran.append(AYAK_IZI * math.exp(c) / b['a'])
    oran = np.array(oran)
    out(f'- sınırlı kare, eğiklik < 5°, eğim −2 sabit: A_uydurma/A_gerçek ortanca {np.median(oran):.3f}, '
        f'%10–90 {np.percentile(oran, 10):.3f}–{np.percentile(oran, 90):.3f}, {len(oran)} bölüm (ölçülen)')
    out('\n| grup | ρ_ölç bandı | kare | ln(ρ/model) ortanca | %10…%90 |\n|---|---|---|---|---|')
    for ad, bs in (('düz', duz), ('W5', w5)):
        L, H = [], []
        for b in bs:
            if not b['a']:
                continue
            m, d = b['m'], b['d']
            t = m['t_yakalama']
            eg = np.interp(t, d['t_gz'], d['egiklik'])
            s = ((t >= b['t0']) & (t <= b['t1']) & (m['view_bounded'] == 0) & (eg < 5)
                 & (m['rho'] > 0) & (m['h_kamera_gercek'] > 0.3))
            model = np.minimum(1.0, b['a'] / (AYAK_IZI * m['h_kamera_gercek'][s] ** 2))
            L += list(np.log(m['rho'][s]) - np.log(model))
            H += list(m['rho'][s])
        L, H = np.array(L), np.array(H)
        for lo, hi in ((0, 0.5), (0.5, 0.75), (0.75, 0.99)):
            s = (H >= lo) & (H < hi)
            if s.any():
                out(f'| {ad}, kadraja sığmayan | {lo:.2f}–{hi:.2f} | {s.sum()} | {np.median(L[s]):+.3f} '
                    f'| {np.percentile(L[s], 10):+.3f}…{np.percentile(L[s], 90):+.3f} |')


def senaryo(ad):
    """'k1_v0.4_veri_w5_t1' -> 'k1'; 'k3_parca_veri_w5_t3' -> 'k3_parca'; 'kol0_...' -> 'kol0'.

    Sibling runs of one scenario share a policy and a start, so they are not
    independent samples: leaving one out still lets its siblings tune for it.
    """
    on = ad.split('_veri_')[0]
    return on[:2] if on.startswith(('k1_', 'k2_')) else on


def _en_kotu(x):
    """The value with the largest magnitude, sign kept."""
    x = np.asarray(x, float)
    return float(x[np.nanargmax(np.abs(x))])


def cmd_loo(a, out):
    """Kalman sigmas chosen without the episode (LOO) and without its scenario (LSO)."""
    w5 = bolumler(a.kok, 'k[1-3]*/veri_w5/*') + bolumler(a.kok, 'kol0/veri_w5/*')
    pen = [b for b in w5 if b['n_sinirli'] >= PENCERE_KARE]
    siz = [b for b in w5 if b['n_sinirli'] < PENCERE_KARE]
    w3 = bolumler(a.kok, 'k[13]*/veri_w3/*') + bolumler(a.kok, 'kol0/veri_w3/*')
    izgara = list(itertools.product((0.01, 0.02, 0.03, 0.05, 0.08), (0.2, 0.35, 0.5, 0.7),
                                    (0.3, 0.5, 0.7, 1.0)))
    # one run per (grid point, episode); both validations only re-read this table
    E = np.full((len(izgara), len(pen)), np.nan)
    V = np.full_like(E, np.nan)
    for gi, (so, sx, sc) in enumerate(izgara):
        for bi, b in enumerate(pen):
            o = olc(b, kos(b, yapici('kalman', so=so, sx=sx, sc=sc)))
            E[gi, bi], V[gi, bi] = o['e2'], o['v_td']
    hedef = np.abs(E)
    # the fixed-gain arms need no tuning: one run each
    sabit = {}
    for kx, kc in ((2.0, -2.0), (3.5, -5.0)):
        R = [olc(b, kos(b, yapici('sabit', kx=kx, kc=kc))) for b in pen]
        sabit[(kx, kc)] = (np.array([o['e2'] for o in R]), np.array([o['v_td'] for o in R]))

    def sec(egit):
        skor = np.nanmean(hedef[:, egit], axis=1)
        gi = int(np.nanargmin(skor))
        return gi, skor[gi]

    out(f'\n### Kalman σ, dışarıda bırakarak (W5 pencereli, {len(pen)} bölüm)\n\n{ACIK_CEVRIM}\n')
    out(f'Izgara σ_ölçüm × σ_x0 × σ_c0 = {len(izgara)} nokta. Eğitim amacı: 2 m\'deki |hata| ortalaması. '
        f'Dışarıdaki bölüm ya da senaryo ayara hiç girmez.\n')
    out('#### Birini dışarıda bırak (bölüm, LOO)\n')
    out('| dışarıdaki bölüm | seçilen σ_ölçüm / σ_x0 / σ_c0 | eğitim |hata| ort | 2 m hatası | v_temas_hesap |\n'
        '|---|---|---|---|---|')
    loo_e, loo_v, secilen = np.full(len(pen), np.nan), np.full(len(pen), np.nan), []
    for bi, b in enumerate(pen):
        gi, s = sec([k for k in range(len(pen)) if k != bi])
        secilen.append(izgara[gi])
        loo_e[bi], loo_v[bi] = E[gi, bi], V[gi, bi]
        so, sx, sc = izgara[gi]
        out(f'| {b["ad"]} | {so} / {sx} / {sc} | {s:.2f} | {E[gi, bi]:+.2f} | {V[gi, bi]:.2f} |')

    out('\n#### Senaryoyu dışarıda bırak (kardeş koşular birlikte, LSO)\n')
    gruplar = {}
    for bi, b in enumerate(pen):
        gruplar.setdefault(senaryo(b['ad']), []).append(bi)
    out('| dışarıdaki senaryo (bölüm) | seçilen σ | Kalman 2 m hatası ortanca / en kötü | Kalman v_temas en kötü '
        '| aynı bölümler, LOO en kötü | sabit 3.5/−5 2 m hatası ortanca / en kötü | sabit 3.5/−5 v_temas en kötü |\n'
        '|---|---|---|---|---|---|---|')
    lso_e, lso_v = np.full(len(pen), np.nan), np.full(len(pen), np.nan)
    s35e, s35v = sabit[(3.5, -5.0)]
    for g, idx in gruplar.items():
        gi, _ = sec([k for k in range(len(pen)) if k not in idx])
        lso_e[idx], lso_v[idx] = E[gi, idx], V[gi, idx]
        so, sx, sc = izgara[gi]
        out(f'| {g} ({len(idx)}) | {so} / {sx} / {sc} | {np.median(E[gi, idx]):+.2f} / {_en_kotu(E[gi, idx]):+.2f} '
            f'| {np.max(V[gi, idx]):.2f} | {_en_kotu(loo_e[idx]):+.2f} '
            f'| {np.median(s35e[idx]):+.2f} / {_en_kotu(s35e[idx]):+.2f} | {np.max(s35v[idx]):.2f} |')

    out('\n#### Yan yana (11 bölüm, dışarıdaki değerler)\n')
    out('| kol | 2 m hatası ortanca | ortalama mutlak hata | en kötü (işaretli) | v_temas_hesap ortanca | v_temas_hesap en kötü |\n'
        '|---|---|---|---|---|---|')
    satir = [('Kalman, bölüm dışarıda (LOO)', loo_e, loo_v), ('Kalman, senaryo dışarıda (LSO)', lso_e, lso_v),
             ('sabit 3.5/−5 (ayarsız)', s35e, s35v), ('sabit 2/−2 (ayarsız)', *sabit[(2.0, -2.0)])]
    for ad, e_, v_ in satir:
        out(f'| {ad} | {np.median(e_):+.2f} | {np.mean(np.abs(e_)):.2f} | {_en_kotu(e_):+.2f} '
            f'| {np.median(v_):.2f} | {np.max(v_):.2f} |')
    tum = int(np.nanargmin(np.nanmean(hedef, axis=1)))
    out(f'\n- **iyimser (ayar ve sınama aynı 11 bölüm):** {izgara[tum]}, ortalama mutlak hata {np.nanmean(hedef[tum]):.2f} m')
    vgi = izgara.index((0.02, 0.5, 0.7))
    out(f'- **plan sayfasındaki σ (0.02 / 0.5 / 0.7):** ortalama mutlak hata {np.nanmean(hedef[vgi]):.2f}, '
        f'en kötü {_en_kotu(E[vgi]):+.2f} m')
    say = {}
    for s in secilen:
        say[s] = say.get(s, 0) + 1
    sik = max(say, key=say.get)
    out(f'- **LOO seçiminin kararlılığı:** {len(say)} farklı σ üçlüsü; en sık {sik} ({say[sik]}/{len(pen)} turda)')
    out(f'\nEn sık seçilenle gerileme sınaması:\n\n{TABLO_BASLIK}')
    so, sx, sc = sik
    out(ozet_satir(f'kalman {so}/{sx}/{sc}, W5 penceresiz', siz, yapici('kalman', so=so, sx=sx, sc=sc)))
    out(ozet_satir(f'kalman {so}/{sx}/{sc}, W3 düz', w3, yapici('kalman', so=so, sx=sx, sc=sc)))
    out(ozet_satir('kalman 0.02/0.5/0.7, W3 düz', w3, yapici('kalman')))


def cmd_nu0(a, out):
    """Is nu at the first usable frame ~0 by construction?

    mapping_node projects every pixel onto the plane z = 0 of the EKF frame
    with altitude_agl = -z (no rangefinder, no camera offset), so the map
    scales lengths by h_ekf / h_camera and areas by its square. If the map is
    built where VALIDATE starts (the search altitude), c0 - 2 x0 cancels the
    height error, and nu0 keeps only the camera offset and the grid's own
    area error.
    """
    w5 = bolumler(a.kok, 'k[1-3]*/veri_w5/*') + bolumler(a.kok, 'kol0/veri_w5/*')
    w3 = bolumler(a.kok, 'k[13]*/veri_w3/*') + bolumler(a.kok, 'kol0/veri_w3/*')
    out(f'\n### ν₀ yapı gereği mi ≈ 0? (harita alanı aynı EKF yüksekliğiyle izdüşürülüyor)\n\n{ACIK_CEVRIM}\n')
    out('| grup | bölüm | IPM\'in öngördüğü A₀/A = (h_ekf₀/h_kamera₀)² | ölçülen A₀/A | ölçülen / öngörülen '
        '| ν₀ hesap = 2 ln((h_ekf₀+0.09)/h_kamera₀) − ln(A₀/A) | ν₀ ölçülen (ilk kare) | abs(ν₀) > 0.5 |\n'
        '|---|---|---|---|---|---|---|---|')
    for ad, bs in (('W5 pencereli', [b for b in w5 if b['n_sinirli'] >= PENCERE_KARE]),
                   ('W5 penceresiz', [b for b in w5 if b['n_sinirli'] < PENCERE_KARE]), ('W3 düz', w3)):
        on, ol, nh, nm = [], [], [], []
        for b in bs:
            if not b['a']:
                continue
            m, d = b['m'], b['d']
            s = np.isfinite(m['h_kamera_gercek'])
            hk0 = float(np.interp(b['t0'], m['t_yakalama'][s], m['h_kamera_gercek'][s]))
            he0 = float(np.interp(b['t0'], d['t_gz'], d['h_ekf']))
            on.append((he0 / hk0) ** 2)
            ol.append(b['a0'] / b['a'])
            nh.append(2 * math.log((he0 + KAMERA_OFSETI) / hk0) - math.log(b['a0'] / b['a']))
            nm.append(kos(b, yapici('sabit'))['nu_ilk'])
        on, ol, nh, nm = map(np.array, (on, ol, nh, nm))

        def f(x):
            return f'{np.nanmedian(x):.3f} ({np.nanmin(x):.3f}…{np.nanmax(x):.3f})'

        def g(x):
            if not np.isfinite(x).any():
                return 'kare yok'
            return f'{np.nanmedian(x):+.3f} ({np.nanmin(x):+.3f}…{np.nanmax(x):+.3f})'

        out(f'| {ad} | {len(bs)} | {f(on)} | {f(ol)} | {f(ol / on)} | {g(nh)} | {g(nm)} '
            f'| {int(np.nansum(np.abs(nm) > 0.5))} / {int(np.isfinite(nm).sum())} |')


def _gecikme_ms(b):
    """Lag of vz_ekf behind Gazebo's vertical speed over the descent, ms."""
    d = b['d']
    s = (d['t_gz'] >= b['t0']) & (d['t_gz'] <= b['t1']) & np.isfinite(d['vz_gercek_hesap']) & np.isfinite(d['vz_ekf'])
    a, g = d['vz_ekf'][s], d['vz_gercek_hesap'][s]
    if len(a) < 50:
        return float('nan')
    a, g = a - a.mean(), g - g.mean()
    best, lag = -np.inf, 0
    for k in range(0, 26):  # 0..500 ms at 50 Hz
        c = float(np.dot(a[k:], g[:len(g) - k]))
        if c > best:
            best, lag = c, k
    return lag * 20.0


def cmd_sapma(a, out):
    """Split the W3 error at 2 m into 'end of the window' and 'carried after it'."""
    w3 = bolumler(a.kok, 'k[13]*/veri_w3/*') + bolumler(a.kok, 'kol0/veri_w3/*')
    out(f'\n### W3 sapması: nerede doğuyor ({len(w3)} bölüm, sabit 2/−2)\n\n{ACIK_CEVRIM}\n')
    out('| bölüm | son kullanılan karede hata | sonra eklenen | 2 m\'de hata | ∫vz_ekf − Δh_gerçek | Δh_ekf − Δh_gerçek | vz_ekf gecikmesi ms |\n'
        '|---|---|---|---|---|---|---|')
    T = []
    for b in w3:
        r = kos(b, yapici('sabit'))
        o = olc(b, r)
        m, d = b['m'], b['d']
        s = np.isfinite(m['h_kamera_gercek'])
        hg = np.interp(r['t'], m['t_yakalama'][s], m['h_kamera_gercek'][s])
        err = r['h'] - hg
        if not len(r['kul_t']):
            continue
        ks = int(np.searchsorted(r['t'], r['kul_t'][-1]))
        k2 = np.nonzero(hg <= 2)[0]
        if not len(k2) or ks >= k2[0]:
            continue
        k2 = int(k2[0])
        t_a, t_b = r['t'][ks], r['t'][k2]
        sel = (d['t_gz'] >= t_a) & (d['t_gz'] < t_b)
        dt = np.diff(d['t_gz'][sel], append=d['t_gz'][sel][-1] + 0.02)
        int_vz = float(np.sum(d['vz_ekf'][sel] * dt))
        dh_g = float(hg[ks] - hg[k2])
        dh_e = float(np.interp(t_a, d['t_gz'], d['h_ekf']) - np.interp(t_b, d['t_gz'], d['h_ekf']))
        row = (err[ks], err[k2] - err[ks], err[k2], int_vz - dh_g, dh_e - dh_g, _gecikme_ms(b))
        T.append(row)
        out(f'| {b["ad"]} | {row[0]:+.2f} | {row[1]:+.2f} | {row[2]:+.2f} | {row[3]:+.2f} | {row[4]:+.2f} | {row[5]:.0f} |')
    T = np.array(T)
    out(f'| **ortanca** | **{np.median(T[:, 0]):+.2f}** | **{np.median(T[:, 1]):+.2f}** | **{np.median(T[:, 2]):+.2f}** '
        f'| **{np.median(T[:, 3]):+.2f}** | **{np.median(T[:, 4]):+.2f}** | **{np.nanmedian(T[:, 5]):.0f}** |')
    out(f'\nİlerletme kaynağı değişince (aynı kapılar, sabit 2/−2):\n\n{TABLO_BASLIK}')
    out(ozet_satir('W3, ilerletme vz_ekf (senin denklemin)', w3, yapici('sabit')))
    out(ozet_satir('W3, ilerletme Δh_ekf', w3, yapici('sabit'), ilerletme='h_ekf'))
    w5 = bolumler(a.kok, 'k[1-3]*/veri_w5/*') + bolumler(a.kok, 'kol0/veri_w5/*')
    pen = [b for b in w5 if b['n_sinirli'] >= PENCERE_KARE]
    out(ozet_satir('W5 pencereli, ilerletme vz_ekf', pen, yapici('sabit')))
    out(ozet_satir('W5 pencereli, ilerletme Δh_ekf', pen, yapici('sabit'), ilerletme='h_ekf'))
    out(ozet_satir('W3, kamera ofseti 0 (önceki replay)', w3, yapici('sabit'), ofset=0.0))
    # The bias is born while frames are used, not after: so try the two
    # starting values. The map's area is 1-3% large on W3.
    oran = np.array([b['a0'] / b['a'] for b in w3 if b['a']])
    out(f'\nBaşlangıç değerleri değişince (W3\'te harita alanı / gerçek alan: ortanca {np.median(oran):.3f}, '
        f'{oran.min():.3f}…{oran.max():.3f}):\n\n{TABLO_BASLIK}')
    for ad, bs in (('W3', w3), ('W5 pencereli', pen)):
        for kw, et in (({}, 'EKF h + harita alanı (tanım)'), ({'a0': True}, 'A₀ = gerçek alan'),
                       ({'h0': True}, 'h₀ = gerçek kamera h'), ({'a0': True, 'h0': True}, 'ikisi de gerçek')):
            out(ozet_satir(f'{ad}, başlangıç: {et}', [_baslangic(b, **kw) for b in bs], yapici('sabit')))


def _baslangic(b, a0=False, h0=False):
    """A copy of the episode whose estimator starts from the true area and/or height."""
    c = dict(b)
    if a0 and b['a']:
        c['a0'] = b['a']
    if h0:
        m, d = b['m'], dict(b['d'])
        s = np.isfinite(m['h_kamera_gercek'])
        hk = d['h_ekf'].copy()
        i0 = np.searchsorted(d['t_gz'], b['t0'])
        hk[i0] = float(np.interp(b['t0'], m['t_yakalama'][s], m['h_kamera_gercek'][s])) - KAMERA_OFSETI
        d['h_ekf'] = hk
        c['d'] = d
    return c


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('komut', nargs='?', default='ozet', choices=('ozet', 'model', 'nu0', 'loo', 'sapma', 'hepsi'))
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    p.add_argument('--rapor', default=None, help='also write the markdown to this file')
    a = p.parse_args()
    satirlar = []

    def out(s):
        print(s, flush=True)
        satirlar.append(s)

    komutlar = ('model', 'nu0', 'ozet', 'loo', 'sapma') if a.komut == 'hepsi' else (a.komut,)
    for k in komutlar:
        globals()[f'cmd_{k}'](a, out)
    if a.rapor:
        with open(a.rapor, 'w') as f:
            f.write('\n'.join(satirlar) + '\n')


if __name__ == '__main__':
    main()
