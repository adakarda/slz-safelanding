"""MESSI SORA-7 masks -> downsampled training scenes and scene lists (amendment 6).

Downsampling by an integer factor keeps the most dangerous class present in each
block (person > vehicle > water > structure > terrain-hazard > unknown > safe-hard
> safe-soft), so a person a few pixels wide survives and safe ground can only
shrink, never grow. Scene size in metres comes from the manifest's own GSD.

    python hazirla.py <messi_rl dir> <out dir> <factor>
Writes <out>/{train,test}/*.png and <out>/{train,test,test7}.txt ('mask size_x size_y').
"""
import csv
import os
import sys
from multiprocessing import Pool

import cv2
import numpy as np

RANK = np.array([0, 1, 3, 4, 5, 6, 7, 2], np.uint8)        # class -> priority
CLS = np.argsort(RANK).astype(np.uint8)                    # priority -> class


def shrink(mask, f):
    h, w = (mask.shape[0] // f) * f, (mask.shape[1] // f) * f
    r = RANK[mask[:h, :w]].reshape(h // f, f, w // f, f).max(axis=(1, 3))
    return CLS[r]


def job(a):
    src, dst, f = a
    m = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    if m is None or m.ndim != 2:
        return src, None
    cv2.imwrite(dst, shrink(m, f))
    return src, m.shape


def main(root, out, f):
    man = list(csv.DictReader(open(f'{root}/manifest.csv')))
    jobs, rows = [], []
    for m in man:
        split = 'test' if m['etiket'] == 'test' else 'train'
        os.makedirs(f'{out}/{split}', exist_ok=True)
        name = m['id'].replace('/', '__')
        dst = f'{out}/{split}/{name}.png'
        jobs.append((f"{root}/{m['mask_sora7']}", dst, f))
        g = float(m['gsd_cm']) / 100.0
        rows.append((split, dst, int(m['w']) * g, int(m['h']) * g, m))
    with Pool(6) as p:
        res = dict(p.map(job, jobs, chunksize=8))
    bad = [s for s, shp in res.items() if shp is None]
    print(len(res), 'maske,', len(bad), 'okunamadi', bad[:3])
    for split in ('train', 'test'):
        sel = sorted([r for r in rows if r[0] == split and res.get(f"{root}/{r[4]['mask_sora7']}")], key=lambda r: r[1])
        with open(f'{out}/{split}.txt', 'w') as fh:
            for _, dst, sx, sy, _ in sel:
                fh.write(f'{dst} {sx:.3f} {sy:.3f}\n')
        print(split, len(sel), 'sahne')
        if split == 'test':
            with open(f'{out}/test7.txt', 'w') as fh:
                for _, dst, sx, sy, _ in sel[::3]:
                    fh.write(f'{dst} {sx:.3f} {sy:.3f}\n')
            print('test7', len(sel[::3]), 'sahne:', [os.path.basename(r[1]) for r in sel[::3]])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]))
