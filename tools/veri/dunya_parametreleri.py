#!/usr/bin/env python3
"""Parameter overrides an island world needs, as make_params arguments.

    tools/veri/dunya_parametreleri.py NAME  ->  "node.param=value ..."

obstacle_driver must drive this world's people (its layout file, its world
name for set_pose) or, in a world without any, be off -- otherwise it falls
back to its parameter defaults and teleports models that do not exist,
publishing a truth topic about nobody.
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))
DIRS = (os.path.join(WS, 'src', 'eland_sim', 'worlds', 'veri'),
        os.path.join(os.path.expanduser('~'), 'eland_veri', 'dunyalar'))


def world_yaml(name):
    if name.endswith('.sdf'):
        return name[:-4] + '.yaml'
    for d in DIRS:
        p = os.path.join(d, name + '.yaml')
        if os.path.exists(p):
            return p
    raise SystemExit(f'dunya yaml bulunamadi: {name}')


def main():
    path = world_yaml(sys.argv[1])
    d = yaml.safe_load(open(path))
    args = [f"obstacle_driver.world_name={d['gz_world']}"]
    if d.get('hareketli_kisi', 0) > 0:
        args.append(f"obstacle_driver.mob_layout_file={d['mob_layout_file']}")
    else:
        args.append('obstacle_driver.enable=false')
    print(' '.join(args))


if __name__ == '__main__':
    main()
