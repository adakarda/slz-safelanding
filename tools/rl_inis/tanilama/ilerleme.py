"""Kosularin anlik ilerlemesi ve son egitim bolumlerindeki basari: python ilerleme.py <kos klasoru>..."""
import csv
import glob
import os
import sys

K = os.path.expanduser('~/rl_inis/kos')
for k in sys.argv[1:]:
    d = os.path.join(K, k)
    r = list(csv.DictReader(open(os.path.join(d, 'progress.csv'))))[-1]
    eps = []
    for p in glob.glob(os.path.join(d, 'monitor_[0-9].monitor.csv')):
        with open(p) as f:
            f.readline()
            eps += list(csv.DictReader(f))
    eps.sort(key=lambda e: float(e['t']))
    son = eps[-800:]
    pay = lambda key: 100 * sum(e.get(key) == 'True' for e in son) / len(son)  # noqa: E731
    oc = {}
    for e in son:
        oc[e['outcome']] = oc.get(e['outcome'], 0) + 1
    zemin = f"zemin %{pay('zemin_success'):.1f}" if 'zemin_success' in son[0] else ''
    print(f"{k}: adim {int(r['time/total_timesteps']):,} / 1,000,000, hiz {r['time/fps']} adim/s; "
          f"son {len(son)} bolum: SORA %{pay('sora_success'):.1f} {zemin} {oc}")
