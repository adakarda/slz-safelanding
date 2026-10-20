import sys
import zipfile

z = {i.filename[len('messi_rl/'):]: (i.file_size, f'{i.CRC:08x}') for i in zipfile.ZipFile(sys.argv[1]).infolist()
     if not i.is_dir()}
a = {}
for ln in open(sys.argv[2], encoding='utf-8'):
    p, s, c = ln.rstrip('\n').split('\t')
    a[p] = (int(s), c)
print('zip:', len(z), '| acilmis kopya:', len(a))
print('ikisinde de olup farkli (boyut/CRC):', [p for p in z.keys() & a.keys() if z[p] != a[p]][:10])
print('zipte olup kopyada olmayan:', sorted(z.keys() - a.keys())[:5], len(z.keys() - a.keys()))
print('kopyada olup zipte olmayan:', sorted(a.keys() - z.keys())[:10], len(a.keys() - z.keys()))
