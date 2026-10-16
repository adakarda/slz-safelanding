"""Scene lists, one scene per line, '#' comments.

    photo.jpg mask.png                    MESSI index mask, size from the photo's EXIF/XMP
    photo.jpg mask.png size_x size_y      MESSI index mask, size given
    mask.png size_x size_y                taxonomy (SORA-7) mask, size given (amendment 6)
    mask.png size_x size_y pred:p.png elev:e.png   + v3 prediction / Depth Anything elevation maps (amendment 7)

shard=(k, n) loads only lines k, k+n, k+2n, ... so parallel environments split a
large list instead of each holding all of it. dist_cell_m sets the SORA grid.
"""
import os

import cv2

from .scene import Scene


def _is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def load_list(path, load_photo=False, shard=None, dist_cell_m=0.1):
    scenes = []
    base = os.path.dirname(os.path.abspath(path))
    lines = [ln.split('#', 1)[0].split() for ln in open(path)]
    lines = [ln for ln in lines if ln]
    if shard is not None:
        k, n = shard
        lines = lines[k::n]
    absp = lambda p: p if os.path.isabs(p) else os.path.join(base, p)  # noqa: E731
    for line in lines:
        if len(line) >= 3 and _is_number(line[1]):
            sc = Scene.from_sora7(absp(line[0]), (float(line[1]), float(line[2])), dist_cell_m=dist_cell_m)
            for extra in line[3:]:                      # pred:<png> elev:<png> (amendment 7)
                key, _, val = extra.partition(':')
                arr = cv2.imread(absp(val), cv2.IMREAD_UNCHANGED)
                if arr is None or arr.shape != sc.mask.shape:
                    raise ValueError(f'{val}: missing or not the size of {line[0]}')
                setattr(sc, {'pred': 'pred', 'elev': 'elev'}[key], arr)
        else:
            size = (float(line[2]), float(line[3])) if len(line) >= 4 else None
            sc = Scene.from_messi(absp(line[0]), absp(line[1]), size_m=size, load_photo=load_photo)
            sc.dist_cell = dist_cell_m
        scenes.append(sc)
    if not scenes:
        raise ValueError(f'{path}: no scenes')
    return scenes
