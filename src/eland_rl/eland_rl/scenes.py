"""Scene lists: one 'photo.jpg mask.png [size_x size_y]' line per scene, '#' comments."""
import os

from .scene import Scene


def load_list(path, load_photo=False):
    scenes = []
    base = os.path.dirname(os.path.abspath(path))
    for line in open(path):
        line = line.split('#', 1)[0].split()
        if not line:
            continue
        jpg, mask = (p if os.path.isabs(p) else os.path.join(base, p) for p in line[:2])
        size = (float(line[2]), float(line[3])) if len(line) >= 4 else None
        scenes.append(Scene.from_messi(jpg, mask, size_m=size, load_photo=load_photo))
    if not scenes:
        raise ValueError(f'{path}: no scenes')
    return scenes
