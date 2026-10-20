"""Extract only what RL training needs (SORA-7 masks, manifest, README) into a new, empty directory."""
import os
import sys
import zipfile

zp, out = sys.argv[1], sys.argv[2]
if os.path.exists(out) and os.listdir(out):
    sys.exit(f'{out} bos degil')
os.makedirs(out, exist_ok=True)
z = zipfile.ZipFile(zp)
n = 0
for info in z.infolist():
    name = info.filename
    if info.is_dir() or name.startswith('/') or '..' in name.split('/'):
        continue
    if not (name.startswith('messi_rl/masks_sora7/') or name in ('messi_rl/manifest.csv', 'messi_rl/README.md')):
        continue
    dest = os.path.join(out, name[len('messi_rl/'):])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with z.open(info) as src, open(dest, 'wb') as dst:
        dst.write(src.read())
    n += 1
print(n, 'dosya ->', out)
