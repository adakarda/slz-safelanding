"""K76 (salt okuma): RGB'si olan 173 karede v3_kullanim; v3 dogrulugu kategoriye gore; degerlendirme listelerinin bileşimi."""
import collections
import csv
import io
import sys
import zipfile

import numpy as np

z = zipfile.ZipFile(sys.argv[1])
names = set(z.namelist())
man = {r['id']: r for r in csv.DictReader(io.TextIOWrapper(z.open('messi_rl/manifest.csv'), 'utf-8'))}
rgb = {i for i, r in man.items() if 'messi_rl/' + r['img'] in names}
pred = {r['ad'].replace('__', '/'): r for r in csv.DictReader(open(sys.argv[2], encoding='utf-8'))}
print('RGB kare:', len(rgb), '| v3 tahmini olan:', len(pred), '| ortak:', len(rgb & pred.keys()))

print('\nucus x v3_kullanim (RGB kareleri):')
t = collections.defaultdict(collections.Counter)
for i in rgb:
    t[man[i]['seq']][man[i]['v3_kullanim']] += 1
cats = ['train', 'val', 'kullanilmadi', 'test']
print('| ucus | ' + ' | '.join(cats) + ' | toplam |')
for s in sorted(t):
    print(f'| {s.split("/")[-1]} | ' + ' | '.join(str(t[s][c]) for c in cats) + f' | {sum(t[s].values())} |')
tot = collections.Counter(man[i]['v3_kullanim'] for i in rgb)
print('| toplam | ' + ' | '.join(str(tot[c]) for c in cats) + f' | {len(rgb)} |')

print('\nv3 dogrulugu kategoriye gore (yarim cozunurluk, GT sora7 ile):')
for c in cats:
    ids = [i for i in rgb if man[i]['v3_kullanim'] == c and i in pred]
    if ids:
        acc = np.array([float(pred[i]['dogruluk']) for i in ids]); mi = np.array([float(pred[i]['miou']) for i in ids])
        print(f'| {c} | {len(ids)} | {acc.mean():.3f} ± {acc.std():.3f} | {mi.mean():.3f} ± {mi.std():.3f} |')

for lst in sys.argv[3:]:
    ids = [ln.split()[0].rsplit('/', 1)[1][:-4].replace('__', '/') for ln in open(lst, encoding='utf-8') if ln.strip()]
    print(f'\n{lst.rsplit("/", 1)[1]}: {len(ids)} kare ->', dict(collections.Counter(man[i]['v3_kullanim'] for i in ids)))
