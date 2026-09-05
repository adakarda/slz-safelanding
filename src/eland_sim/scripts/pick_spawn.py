#!/usr/bin/env python3
"""Pick a spawn pose for the aircraft that is not on top of anything.

WHY THIS EXISTS

Every run started the vehicle at the world origin, so every run tested the
same twenty metres of grass. A landing algorithm that only ever sees one
neighbourhood is only ever tested against one neighbourhood.

WHAT COUNTS AS AN OBSTACLE

Models taller than `--obstacle-height`, plus the paths the dynamic obstacles
drive along. Everything flatter than that is paint on the ground -- the roads,
the gravel and dirt patches and the pond are 2 cm boxes -- and standing on
paint is not a collision. Their class still matters to the landing decision,
which is the point of having them, but not to where the aircraft may sit at
the start.

REPRODUCIBILITY

Prints the seed and the pose it chose, both of which go into the run log.
A run is repeated either by passing the same `--seed`, or by passing the pose
straight back as `--pose x,y,z,r,p,yaw`. The second is the stronger one: it
does not depend on this file staying the same.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
WORLD = os.path.join(PKG, 'worlds', 'eland_test.sdf')
PARAMS = os.path.join(PKG, 'config', 'eland_params.yaml')


def _floats(text, n):
    parts = [float(p) for p in text.split()]
    return (parts + [0.0] * n)[:n]


def _geometry_extent(geom):
    """(half-length along the long axis, radius, top height, long axis is x).

    Obstacles are capsules, not discs. A fence is twelve metres long and
    twelve centimetres thick; describing it by the half-diagonal of its
    bounding box gives a six-metre disc, and a route asked to keep four
    metres from that has to stay ten metres from a fence it could pass a
    metre away from. Measured cost of the disc version: every one of 300
    candidate routes rejected.
    """
    box = geom.find('box')
    if box is not None:
        sx, sy, sz = _floats(box.find('size').text, 3)
        if sx >= sy:
            return max(0.0, (sx - sy) / 2.0), sy / 2.0, sz / 2.0, True
        return max(0.0, (sy - sx) / 2.0), sx / 2.0, sz / 2.0, False
    cyl = geom.find('cylinder')
    if cyl is not None:
        r = float(cyl.find('radius').text)
        length = float(cyl.find('length').text)
        return 0.0, r, length / 2.0, True
    sph = geom.find('sphere')
    if sph is not None:
        r = float(sph.find('radius').text)
        return 0.0, r, r, True
    plane = geom.find('plane')
    if plane is not None:
        # The ground itself. Infinite in extent, zero in height, never an
        # obstacle -- returning a huge radius here would reject every pose.
        return 0.0, 0.0, 0.0, True
    return 0.0, 0.0, 0.0, True


#: `--` inside an XML comment is illegal, and every comment in this project
#: uses it as a dash. libsdformat parses the world anyway (TinyXML is
#: lenient), Python's parser does not, so the comments come out before parsing
#: rather than being rewritten to suit a reader that only this script has.
COMMENT = re.compile(r'<!--.*?-->', re.S)


def obstacles_from_world(path, min_height):
    """[(ax, ay, bx, by, radius, name)] for every model tall enough to matter.

    Each obstacle is a capsule: a segment with a radius. A pole or a tree has
    a zero-length segment and is a disc; a fence or a building wall is a line
    with a thickness. Distance to the obstacle is then distance to that
    segment minus the radius.
    """
    with open(path, 'r', encoding='utf-8') as handle:
        text = COMMENT.sub('', handle.read())
    root = ET.fromstring(text)
    world = root.find('world')
    out = []
    for model in world.findall('model'):
        name = model.get('name', '')
        pose = model.find('pose')
        mx, my, _mz = _floats(pose.text, 3) if pose is not None else (0.0, 0.0, 0.0)
        yaw = _floats(pose.text, 6)[5] if pose is not None else 0.0
        radius = 0.0
        half_len = 0.0
        along_x = True
        top = 0.0
        for link in model.findall('link'):
            for tag in ('visual', 'collision'):
                for vis in link.findall(tag):
                    geom = vis.find('geometry')
                    if geom is None:
                        continue
                    hl, r, h, ax_is_x = _geometry_extent(geom)
                    vpose = vis.find('pose')
                    ox, oy, oz = _floats(vpose.text, 3) if vpose is not None else (0.0, 0.0, 0.0)
                    if r + math.hypot(ox, oy) > radius or hl > half_len:
                        radius = max(radius, r + math.hypot(ox, oy))
                        if hl > half_len:
                            half_len, along_x = hl, ax_is_x
                    top = max(top, oz + h)
        if top >= min_height and radius > 0.0:
            heading = yaw if along_x else yaw + math.pi / 2.0
            dx = math.cos(heading) * half_len
            dy = math.sin(heading) * half_len
            out.append((mx - dx, my - dy, mx + dx, my + dy, radius, name))
    return out


def obstacle_paths(params_path):
    """[(x0, y0, x1, y1)] for the routes the moving obstacles run along."""
    try:
        import yaml
        with open(params_path, 'r', encoding='utf-8') as handle:
            doc = yaml.safe_load(handle)
        p = doc['obstacle_driver']['ros__parameters']
    except Exception:  # noqa: BLE001 - a missing scenario is not fatal here
        return []
    legs = []
    for a, b in (('person_start', 'person_goal'), ('vehicle_start', 'vehicle_goal')):
        if a in p and b in p:
            legs.append((float(p[a][0]), float(p[a][1]),
                         float(p[b][0]), float(p[b][1])))
    return legs


def _point_segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return math.hypot(px - ax, py - ay)
    s = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    return math.hypot(px - (ax + s * dx), py - (ay + s * dy))


def pick(bounds, clearance, path_clearance, obstacles, paths, rng, tries=500):
    x0, y0, x1, y1 = bounds
    for _ in range(tries):
        x = rng.uniform(x0, x1)
        y = rng.uniform(y0, y1)
        if any(_point_segment_distance(x, y, ax, ay, bx, by) < r + clearance
               for ax, ay, bx, by, r, _n in obstacles):
            continue
        if any(_point_segment_distance(x, y, *leg) < path_clearance
               for leg in paths):
            continue
        return x, y
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--world', default=WORLD)
    ap.add_argument('--params', default=PARAMS)
    ap.add_argument('--seed', type=int, default=None,
                    help='omit for a fresh random pose; the seed used is printed')
    ap.add_argument('--bounds', default='-25,-25,25,25',
                    help='x0,y0,x1,y1 the spawn is drawn from')
    # 6 m: an x500 is half a metre across, so this is not about fitting. It is
    # about not starting the run already inside the exclusion zone of the
    # thing being avoided, which would make the first landing decision a
    # foregone conclusion.
    ap.add_argument('--clearance', type=float, default=6.0,
                    help='metres from the edge of any standing obstacle')
    ap.add_argument('--path-clearance', type=float, default=8.0,
                    help='metres from the routes the moving obstacles run')
    ap.add_argument('--obstacle-height', type=float, default=0.5,
                    help='models shorter than this are ground paint, not obstacles')
    ap.add_argument('--yaw', choices=['random', 'zero'], default='random')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1 << 30)
    rng = random.Random(seed)

    obstacles = obstacles_from_world(args.world, args.obstacle_height)
    paths = obstacle_paths(args.params)
    bounds = tuple(float(v) for v in args.bounds.split(','))

    spot = pick(bounds, args.clearance, args.path_clearance, obstacles, paths, rng)
    if spot is None:
        print(f'pick_spawn: no clear pose found in {args.bounds} after 500 '
              f'tries; falling back to the origin', file=sys.stderr)
        spot = (0.0, 0.0)

    yaw = rng.uniform(-math.pi, math.pi) if args.yaw == 'random' else 0.0
    x, y = spot

    if args.verbose:
        print(f'pick_spawn: {len(obstacles)} standing obstacles, '
              f'{len(paths)} obstacle routes', file=sys.stderr)
        nearest = min((_point_segment_distance(x, y, ax, ay, bx, by) - r, n)
                      for ax, ay, bx, by, r, n in obstacles) if obstacles else (0, '-')
        print(f'pick_spawn: nearest obstacle {nearest[1]} at '
              f'{nearest[0]:.1f} m', file=sys.stderr)

    # Two lines: the pose for PX4_GZ_MODEL_POSE, and the seed, so the caller
    # can log both without parsing anything.
    print(f'{x:.2f},{y:.2f},0,0,0,{yaw:.4f}')
    print(seed)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
