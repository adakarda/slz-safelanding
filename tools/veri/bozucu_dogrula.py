#!/usr/bin/env python3
"""Was the Asama 5 disturber really applied? Numbers only.

    tools/veri/bozucu_dogrula.py [--kok ~/eland_veri] [--kare 5] [--cikti DIR]

1. Per episode, from the recorded mask table: d = rho_bozuk - rho_temiz over
   the frames that have both (paired by capture stamp): max |d|, p99 |d|,
   mean |d|, and the share of frames with d != 0. Whole recording and
   VALIDATE only.
2. Changed pixels between the clean and the disturbed mask for a few frames.
   The recorder kept only the clean masks (maskeler.npz), not the disturbed
   ones, so tools/veri/bozucu.py's own disturb() is applied offline to the
   saved clean frames (same code, same level, the episode's seed). This shows
   what the disturber does to these frames, not the exact pixels of the
   online run (its random stream had advanced over earlier frames).
   'tekrar' is replayed as in bozucu.py (hold every level+1 frames over the
   saved sequence); 'gecikme' changes no pixel, only the arrival time.
3. view_bounded share (clean and disturbed), whole recording and VALIDATE,
   with the median rho.
"""
import argparse
import glob
import json
import os
import re
import sys
import types

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dogrula import load_csv  # noqa: E402

SAFE = (0, 1)


def disturber(tur, seviye, tohum):
    """bozucu.Bozucu.disturb without a ROS node around it."""
    import bozucu  # noqa: E402  (needs rclpy importable, not running)
    obj = types.SimpleNamespace(a=types.SimpleNamespace(tur=tur, seviye=seviye),
                                rng=np.random.default_rng(tohum), n_kayip=0)
    return lambda m: bozucu.Bozucu.disturb(obj, m)


def centre_region(m):
    import cv2
    safe = np.isin(m, SAFE).astype(np.uint8)
    _, labels = cv2.connectedComponents(safe, connectivity=8)
    lab = labels[m.shape[0] // 2, m.shape[1] // 2]
    return 0 if lab == 0 else int(np.count_nonzero(labels == lab))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--kok', default=os.path.expanduser('~/eland_veri'))
    p.add_argument('--kare', type=int, default=5)
    p.add_argument('--cikti', default=None)
    a = p.parse_args()
    eps = sorted(glob.glob(os.path.join(a.kok, 'a5_*', 'veri_w3', '*')))
    rows1, rows2, rows3 = [], [], []
    for ep in eps:
        name = os.path.basename(ep)
        tur_sev = re.search(r'_t[0-9]+_(.+)$', name).group(1)
        tur = re.match(r'[a-z]+', tur_sev).group(0)
        seviye = float(tur_sev[len(tur):])
        tohum = int(re.search(r'_t([0-9]+)_', name).group(1))
        m = load_csv(os.path.join(ep, 'maske_olaylari.csv'))
        d = load_csv(os.path.join(ep, 'duzenli.csv'))
        oz = json.load(open(os.path.join(ep, 'ep_ozet.json')))
        tv = oz.get('t_validate')
        tc = oz.get('t_commit') or oz.get('t_temas_gercek') or np.inf
        both = np.isfinite(m['rho_bozuk']) & np.isfinite(m['rho_temiz'])
        val = both & (m['t_yakalama'] >= (tv or np.inf)) & (m['t_yakalama'] <= tc)
        for etiket, sel in (('tum', both), ('VALIDATE', val)):
            dd = (m['rho_bozuk'] - m['rho_temiz'])[sel]
            ad = np.abs(dd)
            rows1.append((name, etiket, int(sel.sum()), int(both.size),
                          float(ad.max()) if ad.size else np.nan,
                          float(np.percentile(ad, 99)) if ad.size else np.nan,
                          float(ad.mean()) if ad.size else np.nan,
                          float(np.mean(dd != 0)) if ad.size else np.nan))
            vb = m['view_bounded'][sel]
            vbb = m['view_bounded_bozuk'][sel]
            rows3.append((name, etiket, int(sel.sum()), float(np.mean(vb == 1)) if vb.size else np.nan,
                          float(np.mean(vbb == 1)) if vbb.size else np.nan,
                          float(np.median(m['rho_temiz'][sel])) if sel.any() else np.nan))
        # 2. offline re-application on saved clean frames
        z = np.load(os.path.join(ep, 'maskeler.npz'))
        masks, tcap = z['maskeler'], z['t_yakalama']
        if tv is not None:
            inval = np.nonzero((tcap >= tv) & (tcap <= tc))[0]
        else:
            inval = np.arange(len(masks))
        if len(inval) == 0:
            continue
        pick = inval[np.linspace(0, len(inval) - 1, a.kare).astype(int)]
        if tur in ('sinir', 'cevir', 'kayip'):
            f = disturber(tur, seviye, tohum)
            # 'kayip' fires on 5 % of frames, so a handful of frames usually
            # shows nothing; the same frames are also run with the level at 1.0
            # (always fires), labelled, to show what a firing does to them.
            f1 = disturber(tur, 1.0, tohum) if tur == 'kayip' else None
            for i in pick:
                clean = masks[i]
                bad = f(clean)
                h = np.interp(tcap[i], d['t_gz'], d['h_gercek_zemin'])
                rows2.append((name, round(float(tcap[i]), 2), round(float(h), 1),
                              int(np.count_nonzero(bad != clean)), clean.size,
                              centre_region(clean), centre_region(bad), ''))
                if f1 is not None:
                    bad1 = f1(clean)
                    rows2.append((name, round(float(tcap[i]), 2), round(float(h), 1),
                                  int(np.count_nonzero(bad1 != clean)), clean.size,
                                  centre_region(clean), centre_region(bad1),
                                  'seviye 1.0 ile zorla tetiklendi'))
        elif tur == 'tekrar':
            k = int(seviye) + 1
            held = None
            for j in range(len(masks)):
                if held is None or j % k == 0:
                    held = masks[j]
                if j in set(pick.tolist()):
                    h = np.interp(tcap[j], d['t_gz'], d['h_gercek_zemin'])
                    rows2.append((name, round(float(tcap[j]), 2), round(float(h), 1),
                                  int(np.count_nonzero(held != masks[j])), masks[j].size,
                                  centre_region(masks[j]), centre_region(held),
                                  'tutulan kare' if j % k == 0 else f'{j % k} kare onceki icerik'))
        elif tur == 'gecikme':
            for i in pick:
                h = np.interp(tcap[i], d['t_gz'], d['h_gercek_zemin'])
                rows2.append((name, round(float(tcap[i]), 2), round(float(h), 1), 0, masks[i].size,
                              centre_region(masks[i]), centre_region(masks[i]),
                              'icerik ayni, yalniz 0.2 s gec'))

    out = []
    out.append('## 1. rho_bozuk - rho_temiz (kayitli, yakalama damgasiyla eslenmis)\n')
    out.append('| bolum | aralik | eslesen kare / toplam | max abs(d) | p99 abs(d) | ort abs(d) | d != 0 kare orani |')
    out.append('|---|---|---|---|---|---|---|')
    for r in rows1:
        out.append(f'| {r[0]} | {r[1]} | {r[2]} / {r[3]} | {r[4]:.6f} | {r[5]:.6f} | {r[6]:.6f} | {r[7]:.3f} |')
    out.append('\n## 2. Degisen piksel (kayitli temiz kareye bozucu.py disturb() cevrimdisi uygulandi; VALIDATE icinden esit aralikli kareler)\n')
    out.append('| bolum | t_yakalama (s) | h_gercek (m) | degisen piksel / toplam | merkez bolge pikseli temiz | merkez bolge pikseli bozuk | not |')
    out.append('|---|---|---|---|---|---|---|')
    for r in rows2:
        out.append(f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} / {r[4]} | {r[5]} | {r[6]} | {r[7]} |')
    out.append('\n## 3. view_bounded (kayitli)\n')
    out.append('| bolum | aralik | kare | view_bounded=1 orani (temiz) | view_bounded_bozuk=1 orani | ortanca rho_temiz |')
    out.append('|---|---|---|---|---|---|')
    for r in rows3:
        out.append(f'| {r[0]} | {r[1]} | {r[2]} | {r[3]:.3f} | {r[4]:.3f} | {r[5]:.4f} |')
    text = '\n'.join(out)
    print(text)
    if a.cikti:
        os.makedirs(a.cikti, exist_ok=True)
        open(os.path.join(a.cikti, 'bozucu_dogrula.md'), 'w').write(text + '\n')


if __name__ == '__main__':
    main()
