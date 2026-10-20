"""Asama 0: zip'i acmadan oku. Sadece listeleme ve kucuk metin dosyalarini okuma."""
import collections
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
infos = z.infolist()
print('dosya sayisi:', len(infos), '| toplam acilmis MB:', round(sum(i.file_size for i in infos) / 2**20, 1))
dirs = collections.Counter()
ext = collections.Counter()
for i in infos:
    if i.is_dir():
        continue
    parts = i.filename.split('/')
    dirs['/'.join(parts[:-1])] += 1
    ext[i.filename.rsplit('.', 1)[-1].lower() if '.' in parts[-1] else '(yok)'] += 1
print('uzantilar:', dict(ext))
print('klasorler (dosya sayisi):')
for d, n in sorted(dirs.items()):
    mb = sum(i.file_size for i in infos if i.filename.startswith(d + '/') and i.filename.count('/') == d.count('/') + 1) / 2**20
    print(f'  {d or "(kok)"}: {n} dosya, {mb:.1f} MB')
txt = [i for i in infos if i.filename.lower().rsplit('.', 1)[-1] in ('csv', 'json', 'yaml', 'yml', 'txt', 'md')]
print('\nmetin dosyalari:', len(txt))
for i in txt:
    print(f'\n=== {i.filename} ({i.file_size} B)')
    data = z.read(i.filename).decode('utf-8', 'replace')
    lines = data.splitlines()
    print(f'  satir: {len(lines)}')
    for ln in lines[:12 if i.filename.lower().endswith('.csv') else 80]:
        print('  |', ln[:220])
