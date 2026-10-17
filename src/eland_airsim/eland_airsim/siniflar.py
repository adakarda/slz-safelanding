"""AirSim object names -> SORA classes, and segmentation images -> class maps.

AirSim paints every object with the colour of its segmentation ID (data/seg_rgbs.txt). Every object
of SORA class c gets the ID c + 1 and everything else 0, so one segmentation image decodes to
"class + 1", with 0 = unknown. That is the label convention gz-sim's labels map follows in this
project (perception_node.remap_gt), so the perception chain reads AirSim and Gazebo the same way.

AirSim matches the names with std::regex, which is case sensitive and has no inline flags, so the
patterns are written out case-insensitively here (ci()).
"""
import os
import re

import numpy as np

UNKNOWN = 7

#: (SORA class, words). Later rows win where a name matches several (a "CarPark" is a car). The words
#: were checked against the object names of AirSimNH (3884) and CityEnviron (5707) in the M0 pilot:
#: AirSimNH's grass is the Landscape actor; "Garden_Chair", "Car_Porch" (a carport), "Pool_Table",
#: "prp_streetLight" and "PatioFurniture" must not take their first word's class.
WORDS = [
    (0, ['grass', 'lawn', 'field', 'meadow', 'soil', 'dirt', 'turf', 'landscape']),
    (1, ['sidewalk', 'pavement', 'driveway', 'walkway', 'path', 'plaza', 'patio', 'curb', 'kerb']),
    (2, ['road', 'street', 'asphalt', 'parking', 'intersection', 'crosswalk', 'tree', 'bush', 'hedge', 'shrub',
         'foliage', 'pine', 'oak', 'birch', 'fir', 'leaf', 'leaves', 'plant', 'weeds']),
    (3, ['house', 'building', 'roof', 'wall', 'fence', 'garage', 'shed', 'porch', 'chimney', 'pole', 'lamp',
         'sign', 'bench', 'mailbox', 'hydrant', 'trash', 'bin', 'wire', 'door', 'veranda', 'banister', 'stair',
         'steps', 'chair', 'table', 'sofa', 'rock', 'hoop', 'monument', 'power_line', 'cable', 'pipe', 'cladding',
         'shutter', 'support', 'fireplace', 'skateboard', 'light', 'barrier', 'litter', 'palette', 'vent', 'grate',
         'garbage', 'apartment', 'pillar', 'newspaper', 'pot', 'dumpster', 'duct', 'flag', 'pylon', 'electrical',
         'cone', 'skyscraper', 'tower', 'stilts', 'station', 'furniture', 'umbrella', 'plate']),
    (4, ['pool', 'water', 'pond', 'river', 'lake', 'fountain']),
    (5, ['car', 'vehicle', 'truck', 'van', 'suv', 'bus', 'bike', 'bicycle', 'coupe', 'saloon', 'sedan',
         'hatchback', 'taxi', 'dog', 'cat', 'animal', 'deer', 'raccoon']),
    (6, ['person', 'human', 'pedestrian', 'character', 'mannequin', 'people']),
    # names a later word would take: "Bush" holds "bus", "BaseCarPath" holds "car", and so on
    (1, ['pedestrianpath', 'bicyclepath']),
    (2, ['carpath', 'crosswalk', 'bush']),
    (3, ['car_porch', 'carport', 'pool_table']),
]

#: Words per std::regex call. One alternation of 60+ words fails inside AirSim on CityEnviron (the call
#: returned False and that class was left unpainted); short patterns, applied in order, give the same result.
CHUNK = 6


def ci(word):
    """A case-insensitive std::regex fragment for one word: 'car' -> '[Cc][Aa][Rr]'."""
    return ''.join(f'[{ch.upper()}{ch.lower()}]' if ch.isalpha() else re.escape(ch) for ch in word)


def rules(words=WORDS, chunk=CHUNK):
    """[(class, std::regex pattern)] in priority order, at most `chunk` words per pattern."""
    return [(c, '.*(' + '|'.join(ci(w) for w in ws[i:i + chunk]) + ').*')
            for c, ws in words for i in range(0, len(ws), chunk)]


def classify_names(names, words=WORDS):
    """{name: class} for the names a rule matches, with the same priority AirSim will apply."""
    out = {}
    for c, ws in words:
        pat = re.compile('|'.join(re.escape(w) for w in ws), re.I)
        for n in names:
            if pat.search(n):
                out[n] = c
    return out


def assign_ids(client, words=WORDS):
    """Set every object to ID 0, then each class's objects to class + 1.

    Returns {class: [result per pattern]}; AirSim answers False when a pattern matched nothing (or failed).
    """
    client.simSetSegmentationObjectID('.*', 0, True)
    out = {}
    for c, p in rules(words):
        out.setdefault(c, []).append(bool(client.simSetSegmentationObjectID(p, c + 1, True)))
    return out


def palette(path=None):
    """(256, 3) uint8 RGB colours of AirSim's segmentation IDs."""
    path = path or os.path.join(os.path.dirname(__file__), '..', 'data', 'seg_rgbs.txt')
    if not os.path.exists(path):  # installed layout: share/eland_airsim/data
        from ament_index_python.packages import get_package_share_directory
        path = os.path.join(get_package_share_directory('eland_airsim'), 'data', 'seg_rgbs.txt')
    pal = np.zeros((256, 3), np.uint8)
    for line in open(path, encoding='utf-8'):
        m = re.match(r'\s*(\d+)\s*\[(\d+),\s*(\d+),\s*(\d+)\]', line)
        if m:
            pal[int(m.group(1))] = [int(m.group(2)), int(m.group(3)), int(m.group(4))]
    return pal


def decode(seg, pal, channel_order='bgr'):
    """Segmentation image (H, W, 3) -> labels (H, W) uint8: class + 1 where an object of a class shows,
    0 elsewhere (unknown, sky, unmatched objects)."""
    img = seg[..., ::-1] if channel_order == 'bgr' else seg
    key = (img[..., 0].astype(np.int32) << 16) | (img[..., 1].astype(np.int32) << 8) | img[..., 2].astype(np.int32)
    out = np.zeros(key.shape, np.uint8)
    for k in range(1, UNKNOWN + 1):
        r, g, b = (int(v) for v in pal[k])
        out[key == ((r << 16) | (g << 8) | b)] = k
    return out


def labels_to_classes(labels):
    """'class + 1' labels -> SORA classes 0..6, UNKNOWN (7) where the label is 0."""
    return np.where(labels == 0, UNKNOWN, labels.astype(np.int16) - 1).astype(np.uint8)
