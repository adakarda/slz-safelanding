"""Acilmis MESSI kopyasinin dosya listesi, boyut ve CRC32'si (salt okuma)."""
import os
import sys
import zlib

root = sys.argv[1]
for d, _, fs in os.walk(root):
    for f in fs:
        p = os.path.join(d, f)
        c = 0
        with open(p, 'rb') as h:
            while chunk := h.read(1 << 20):
                c = zlib.crc32(chunk, c)
        print(f'{os.path.relpath(p, root)}\t{os.path.getsize(p)}\t{c:08x}')
