"""PX4 parameters.bson (SITL rootfs) -> name: value, without PX4 running. Minimal BSON reader (double, int32).

    python3 param_bson.py ROOTFS/parameters.bson [ROOTFS2/parameters.bson]   (two files: show differences)
"""
import struct
import sys


def oku(path):
    b = open(path, 'rb').read()
    n = struct.unpack_from('<i', b, 0)[0]
    i, out = 4, {}
    while i < n - 1:
        t = b[i]
        i += 1
        j = b.index(b'\0', i)
        name = b[i:j].decode()
        i = j + 1
        if t == 0x01:
            out[name] = round(struct.unpack_from('<d', b, i)[0], 6)
            i += 8
        elif t == 0x10:
            out[name] = struct.unpack_from('<i', b, i)[0]
            i += 4
        else:
            break
    return out


if __name__ == '__main__':
    a = oku(sys.argv[1])
    if len(sys.argv) == 2:
        for k in sorted(a):
            print(k, a[k])
    else:
        b = oku(sys.argv[2])
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                print(f'{k:20s} {str(a.get(k, "-")):>12s} {str(b.get(k, "-")):>12s}')
