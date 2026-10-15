#!/usr/bin/env python3
"""Online-offline equality of the height observer (K14 e).

    tools/veri/gozlemci_esitlik.py BOLUM_KLASORU [--tolerans 1e-4]

Replays one recorded episode's observer inputs -- gozlemci_kare.csv (descent
starts and every /eland/rho frame, with the node time, the stamp and every
value used) and gozlemci.csv (the 50 Hz ticks: node time and vz) -- through
src/eland_mapping/eland_mapping/gozlem_hesap.py with the episode's own
parameters (params.yaml, yukseklik_gozlemci), in the node's own order, and
compares the result with what the node published.

Expected: equal to float32 rounding of the published values (the node and
the replay do the same double arithmetic in the same order). A difference
above that means the replay is not the node: a missing tick row (best-effort
topic), a parameter not as recorded, or a code path that differs.
Writes nothing; prints the comparison.
"""
import argparse
import bisect
import csv
import math
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'src', 'eland_mapping'))
from eland_mapping import gozlem_hesap as G  # noqa: E402

NAN = float('nan')


def f(v):
    return NAN if v in ('', None) else float(v)


def oku(yol):
    with open(yol, newline='') as fh:
        return list(csv.DictReader(fh))


def kur(par, tip):
    eg = float(par.get('egiklik_kapi_deg', 5.0))
    kap = lambda: G.Kapilar(rho_doyum=float(par.get('rho_doyum', 0.75)),  # noqa: E731
                            nu_max=float(par.get('nu_max', 0.5)),
                            sinirli=bool(par.get('sinirli_kapi', True)),
                            egiklik_deg=eg if eg > 0 else None)
    if tip == 'kalman':
        g = G.Kalman(sigma_olcum=float(par.get('sigma_olcum', 0.05)),
                     sigma_x0=float(par.get('sigma_x0', 0.7)),
                     sigma_c0=float(par.get('sigma_c0', 0.7)), kapilar=kap())
    else:
        g = G.Sabit(kx=float(par.get('kx', 2.0)), kc=float(par.get('kc', -2.0)), kapilar=kap())
    return g, G.Dogrudan(kapilar=kap())


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('bolum')
    p.add_argument('--tolerans', type=float, default=1e-4, help='m, on the published heights')
    a = p.parse_args()
    par = yaml.safe_load(open(os.path.join(a.bolum, 'params.yaml')))
    par = (par.get('yukseklik_gozlemci') or {}).get('ros__parameters', {})
    ofset = float(par.get('kamera_ofseti_m', 0.09))
    tikler = oku(os.path.join(a.bolum, 'gozlemci.csv'))
    kareler = oku(os.path.join(a.bolum, 'gozlemci_kare.csv'))
    # ticks in publish order; frames go between the ticks they were processed between
    tikler.sort(key=lambda r: int(r['t_dugum_ns']))
    t_tik = [int(r['t_dugum_ns']) * 1e-9 for r in tikler]
    # Intervals between ticks longer than the 20 ms period are the node's own
    # timing (simulation clock, executor): information, not missing rows.
    bosluk = [round((t_tik[i + 1] - t_tik[i]) * 1000) for i in range(len(t_tik) - 1)]
    uzun = sum(1 for b in bosluk if b > 30)
    print(f'tik satiri {len(tikler)}, kare/baslat satiri {len(kareler)}; 30 ms\'den uzun tik '
          f'araligi {uzun} (en uzun {max(bosluk, default=0)} ms, dugumun kendi zamanlamasi)')

    # The writer may start after the node's first ticks: find the node's tick
    # number of row 0 (offset) from the frames, each of which was processed
    # between tick (tick_sayisi - 1) and tick tick_sayisi.
    adaylar = {}
    for k in kareler:
        if f(k['tur']) == 1.0:
            m = bisect.bisect_left(t_tik, f(k['t_dugum']))
            o = int(f(k['tick_sayisi'])) - m
            adaylar[o] = adaylar.get(o, 0) + 1
    ofs = max(adaylar, key=adaylar.get) if adaylar else 0
    if len(adaylar) > 1:
        print(f'  tik numarasi kaymasi adaylari {adaylar} -> {ofs} (esit zamanli kareler)')
    # Missing tick rows: each frame records how many ticks the node had
    # published before it, so that many rows must lie before (or at) its time.
    eksik = 0
    for k in kareler:
        if f(k['tur']) == 1.0:
            n, t = int(f(k['tick_sayisi'])) - ofs, f(k['t_dugum'])
            if not bisect.bisect_left(t_tik, t) <= n <= bisect.bisect_right(t_tik, t):
                eksik += 1
    print(f'  tik sayisi kayitla tutmayan kare (eksik tik satiri): {eksik}')
    olaylar = [('kare', int(f(k['tick_sayisi'])), j, k) for j, k in enumerate(kareler)]
    olaylar += [('tik', i + ofs, 0, r) for i, r in enumerate(tikler)]
    # a frame with tick_sayisi n was processed after tick n-1 and before tick n
    olaylar.sort(key=lambda e: (e[1], 0 if e[0] == 'kare' else 1, e[2]))

    g = d = None
    tip = par.get('gozlemci_tipi', 'sabit')
    fark_h, fark_hd, fark_x, uyusmayan_kapi, n_tik_karsi, n_kare_karsi = [], [], [], 0, 0, 0
    for tur, _, _, r in olaylar:
        if tur == 'kare':
            if f(r['tur']) == 0.0:
                g, d = kur(par, tip)
                t = f(r['t_dugum'])
                g.baslat(t, f(r['h0_kamera']), f(r['alan0']))
                d.baslat(t, f(r['h0_kamera']), f(r['alan0']))
                continue
            if g is None:
                continue
            t, vz = f(r['t_dugum']), f(r['v_asagi'])
            g.ilerlet(t, vz)
            d.ilerlet(t, vz)
            damga = f(r['damga']) == 1.0
            kg = g.olcum(f(r['t_yakalama']), f(r['rho']), f(r['view_bounded']) == 1.0,
                         f(r['egiklik_deg']), damga_kullan=damga)
            kd = d.olcum(f(r['t_yakalama']), f(r['rho']), f(r['view_bounded']) == 1.0,
                         f(r['egiklik_deg']), damga_kullan=damga)
            uyusmayan_kapi += (kg != int(f(r['kapi_g']))) + (kd != int(f(r['kapi_d'])))
            fark_x += [abs(g.x - f(r['x_g'])), abs(g.c - f(r['c_g'])), abs(d.x - f(r['x_d']))]
            n_kare_karsi += 1
        else:
            if r['gecerli'] != '1':
                if g is not None and n_tik_karsi:
                    g = d = None          # the node ended the descent
                continue
            if g is None:
                continue
            t = int(r['t_dugum_ns']) * 1e-9
            vz = f(r['v_asagi_mps'])
            g.ilerlet(t, vz)
            d.ilerlet(t, vz)
            fark_h.append(abs((g.h - ofset) - f(r['h_gozlemci_m'])))
            fark_hd.append(abs((d.h - ofset) - f(r['h_dogrudan_m'])))
            n_tik_karsi += 1

    def ozet(ad, xs, birim):
        if not xs:
            return f'{ad}: karsilastirma yok'
        xs = [x for x in xs if not math.isnan(x)]
        return f'{ad}: en buyuk {max(xs):.3g} {birim}, ortalama {sum(xs) / len(xs):.3g} {birim}, n {len(xs)}'

    print(f'gozlemci tipi {tip}, kamera ofseti {ofset}')
    print(ozet('  h_gozlemci (tik)', fark_h, 'm'))
    print(ozet('  h_dogrudan (tik)', fark_hd, 'm'))
    print(ozet('  x, c (kare sonrasi)', fark_x, ''))
    print(f'  kapi karari uyusmayan: {uyusmayan_kapi} / {2 * n_kare_karsi}')
    ok = (fark_h and max(fark_h) <= a.tolerans and uyusmayan_kapi == 0
          and (not fark_x or max(fark_x) <= 1e-9) and not eksik)
    print('SONUC:', 'ESIT (sayisal gurultu duzeyinde)' if ok else 'ESIT DEGIL -- nedeni aranmali')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
