"""Extract the JPG photos (images/) of the MESSI package next to its masks."""
import os
import sys
import zipfile

z = zipfile.ZipFile(sys.argv[1])
out = sys.argv[2]
n = 0
for info in z.infolist():
    name = info.filename
    if info.is_dir() or not name.startswith('messi_rl/masks_raw16/') or '..' in name.split('/'):
        continue
    dest = os.path.join(out, name[len('messi_rl/'):])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        with z.open(info) as src, open(dest, 'wb') as dst:
            dst.write(src.read())
    n += 1
print(n, 'ham maske ->', out)
