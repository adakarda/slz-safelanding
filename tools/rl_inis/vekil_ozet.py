"""Duzeltme 10 asama 1 (vekil gorev) ozeti: kodlayici basina 3 tohumun ortalamasi."""
import collections
import json
import statistics as st

v = json.load(open('/home/arda/rl_inis/kos/vekil/vekil.json'))
g = collections.defaultdict(list)
for r in v:
    g[r['encoder']].append(r)
for e, rs in g.items():
    def f(k):
        x = [100 * r[k] for r in rs]
        return f'{st.mean(x):5.1f} ± {st.stdev(x) if len(x) > 1 else 0:3.1f}'
    print(f'{e:13s} n={len(rs)} param {rs[0]["params"] / 1e6:.2f}M  dengeli dogruluk {f("bal_acc")}  '
          f'dogruluk {f("acc")}  alcal-mi {f("descend_acc")}')
