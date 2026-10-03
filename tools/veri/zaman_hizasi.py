#!/usr/bin/env python3
"""Time alignment and structure of one ep.mat, as MATLAB will see it.

    tools/veri/zaman_hizasi.py EP_DIR

Reads ep.mat with scipy (MATLAB is not on this machine) and reports:
  * the structs, their fields, types and lengths -- anything that would
    arrive in MATLAB as something other than a column vector or cellstr;
  * capture -> record delay of the masks (maske_yasi_ms);
  * the 50 Hz grid: spacing, and per channel how old the held value is
    (the *_yas_ms columns) -- the grid itself has no jitter by
    construction, the age distribution is where the timing shows.
"""
import json
import os
import sys

import numpy as np
import scipy.io


def pct(x, q):
    x = x[np.isfinite(x)]
    return float(np.percentile(x, q)) if len(x) else float('nan')


def main():
    ep = sys.argv[1]
    mat = scipy.io.loadmat(os.path.join(ep, 'ep.mat'), squeeze_me=True, struct_as_record=False)
    print(f'## {os.path.basename(ep.rstrip("/"))} — ep.mat\n')
    print('| yapı | alan sayısı | sayısal alan | metin (cell) alan | uzunluk(lar) |')
    print('|---|---|---|---|---|')
    for name in ('duzenli', 'maske', 'karar', 'gecis'):
        s = mat[name]
        fields = s._fieldnames
        num = [f for f in fields if np.asarray(getattr(s, f)).dtype.kind in 'fiu']
        txt = [f for f in fields if f not in num]
        lens = sorted({np.asarray(getattr(s, f)).size for f in fields})
        print(f'| {name} | {len(fields)} | {len(num)} | {len(txt)} ({", ".join(txt)}) | {lens} |')
    oz = json.loads(mat['ozet_json'])
    print(f'\nozet_json: {len(oz)} alan (MATLAB: jsondecode(ozet_json))\n')

    m = mat['maske']
    age = np.asarray(m.maske_yasi_ms, float)
    print(f'maske yakalama -> kayit: p50 {pct(age, 50):.1f} ms, p90 {pct(age, 90):.1f} ms, '
          f'p99 {pct(age, 99):.1f} ms, en çok {np.nanmax(age):.1f} ms (n={len(age)})')
    d = mat['duzenli']
    t = np.asarray(d.t_gz, float)
    dt = np.diff(t)
    print(f'ızgara: {len(t)} satır, aralık {dt.mean() * 1000:.3f} ms, '
          f'std {dt.std() * 1000:.4f} ms, en az/en çok {dt.min() * 1000:.3f}/{dt.max() * 1000:.3f} ms\n')
    print('| kanal | yaş p50 (ms) | p95 | en çok |')
    print('|---|---|---|---|')
    for c in ('h_ekf', 'roll', 'v_cmd', 'v_ref', 'durum', 'h_gercek_zemin', 'landed', 'v_ref_dis'):
        a = getattr(d, c + '_yas_ms', None)
        if a is None:
            continue
        a = np.asarray(a, float)
        print(f'| {c} | {pct(a, 50):.1f} | {pct(a, 95):.1f} | {np.nanmax(a) if np.isfinite(a).any() else float("nan"):.1f} |')


if __name__ == '__main__':
    main()
