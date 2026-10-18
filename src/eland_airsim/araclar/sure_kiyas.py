"""AirSim kollarinda inis suresi ve yatay yol (harita sonuclarindan; tanimlayici)."""
import json
import os
import statistics as st
import sys

G = os.path.expanduser('~/eland_veri/_gunlukler/airsim_faz3')
for ad in sys.argv[1:]:
    rs = [json.loads(x) for x in open(os.path.join(G, ad + '.jsonl.harita.jsonl')) if x.strip()]
    s = [r['sure_s'] for r in rs if r.get('sonuc') == 'indi']
    y = [r['yatay_uzaklik_m'] for r in rs if 'yatay_uzaklik_m' in r]
    z = sum(bool(r.get('zemin_uygun')) for r in rs)
    print(f'{ad:18s} zemin {z}/{len(rs)}  sure ort {st.mean(s):5.1f} s, medyan {st.median(s):5.1f}, '
          f'en az {min(s):5.1f}, en cok {max(s):5.1f}  yatay yol ort {st.mean(y):5.1f} m')
