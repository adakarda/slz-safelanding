#!/usr/bin/env python3
"""Write a parameter-file variant for one run, from the installed defaults.

Usage: make_params.py OUT [node.param=value ...]

Values are parsed as YAML, so booleans and lists work:

    make_params.py /tmp/run.yaml detector_node.trajectory_filter_enabled=false \\
                                 obstacle_driver.person_count=3

Why a whole file rather than `--ros-args -p`: the world generator reads the
same YAML the nodes do, so a run has to hand both of them one document. A
partial file is not an option either -- gen_world.py needs every key it uses,
and a file missing `vehicle_start` fails the run outright.
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'src', 'eland_sim', 'config', 'eland_params.yaml')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    out = sys.argv[1]
    with open(SRC, 'r', encoding='utf-8') as f:
        doc = yaml.safe_load(f)
    for arg in sys.argv[2:]:
        key, _, raw = arg.partition('=')
        node, _, param = key.partition('.')
        if node not in doc:
            print(f'no such node section: {node}', file=sys.stderr)
            return 1
        doc[node]['ros__parameters'][param] = yaml.safe_load(raw)
        print(f'  {node}.{param} = {doc[node]["ros__parameters"][param]!r}')
    with open(out, 'w', encoding='utf-8') as f:
        yaml.safe_dump(doc, f, default_flow_style=False, sort_keys=False)
    print(f'yazildi: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
