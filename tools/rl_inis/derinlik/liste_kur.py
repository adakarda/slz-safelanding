"""Amendment 7 scene lists: photo frames with GT mask, v3 prediction and Depth Anything elevation."""
import csv
import os

import cv2

R = '/home/arda/eland_veri/rl/messi_rl'
D = '/home/arda/eland_veri/rl/messi_ds4'
TEST_SEQ = 'Agamim/Descend/100_0004'
sizes = {}
for ln in open(f'{D}/train.txt'):
    p, sx, sy = ln.split()
    sizes[os.path.basename(p)[:-4]] = (sx, sy)
man = [m for m in csv.DictReader(open(f'{R}/manifest.csv')) if os.path.exists(f"{R}/{m['img']}")]
out = {'train_foto': [], 'test_foto': []}
for m in sorted(man, key=lambda m: m['id']):
    n = m['id'].replace('/', '__')
    gt, pr, el = f'{D}/train/{n}.png', f'{D}/pred/{n}.png', f'{D}/elev/{n}.png'
    shapes = {cv2.imread(x, cv2.IMREAD_UNCHANGED).shape for x in (gt, pr, el)}
    assert len(shapes) == 1, (n, shapes)
    sx, sy = sizes[n]
    out['test_foto' if m['seq'] == TEST_SEQ else 'train_foto'].append(f'{gt} {sx} {sy} pred:{pr} elev:{el}\n')
for k, v in out.items():
    open(f'{D}/{k}.txt', 'w').writelines(v)
    print(k, len(v))
