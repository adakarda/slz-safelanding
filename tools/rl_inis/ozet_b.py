"""B deneyi: biten kosularin val_b32 ozeti (zemin basari, yumusak) yontem basina."""
import glob
import os
import re

for d in sorted(glob.glob(os.path.expanduser('~/rl_inis/kos/b_B*'))):
    f = os.path.join(d, 'eval_val.txt')
    if not os.path.exists(f):
        print(os.path.basename(d), 'degerlendirme yok')
        continue
    lines = open(f).read().splitlines()
    out = []
    for i, ln in enumerate(lines):
        m = re.match(r'^(\w+)\s+SORA basari\s+([\d.]+)', ln)
        if m:
            z = next((re.search(r'zemin basari\s+([\d.]+) %\s+yumusak\s+([\d.]+)', x) for x in lines[i + 1:]
                      if 'zemin basari' in x), None)
            if z and m.group(1) in ('rl', 'rl_kalkan', 'duz_kalkan'):
                out.append(f'{m.group(1)} zemin {z.group(1)} yumusak {z.group(2)}')
    print(os.path.basename(d), ' | '.join(out))
