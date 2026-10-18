"""policy_node'un politika.csv'si: adim sayisi, eylem dagilimi, kalkan mudahalesi, yukseklik araligi, cikarim suresi.

    python3 politika_ozet.py politika.csv
"""
import collections
import csv
import sys

AD = {0: 'dur', 9: 'alcal', 1: 'ileri', 2: 'sol-ileri', 3: 'sol', 4: 'sol-geri', 5: 'geri', 6: 'sag-geri',
      7: 'sag', 8: 'sag-ileri'}
r = list(csv.DictReader(open(sys.argv[1])))
if not r:
    print('politika.csv bos: politika hic adim atmadi')
    sys.exit(1)
ey = collections.Counter(int(x['action']) for x in r)
z = [float(x['z_cam']) for x in r]
ms = sorted(float(x['infer_ms']) for x in r)
kal = sum(int(x.get('kalkan', 0) or 0) for x in r)
print(f'{len(r)} adim ({len(r) * 0.25:.0f} s); kamera yuksekligi {max(z):.1f} -> {min(z):.1f} m; '
      f'kalkan mudahalesi {kal}; cikarim p50 {ms[len(ms) // 2]:.1f} ms')
print('eylemler: ' + ', '.join(f'{AD[a]} {n}' for a, n in ey.most_common()))
print('guvenli pay (ilk/son adim): ' + f"{r[0]['safe_share']} / {r[-1]['safe_share']}")
