"""v4 veri paketinden RL sahneleri (2026-10-25, Arda: "yeni veriyle yeni egitim").

Secim: yalniz olcegi bilinen ve kameranin 20-30 m'de gordugu alana yeten kareler (en az 60 x 45 m):
FloodNet (hepsi ~80 x 60 m) ve MESSI'nin buyuk kareleri. TU Graz (5-30 m irtifa, sahne kucuk) ve VDD (irtifa ve
olcek yok) disarida.
Sinif: masks8 -> RL siniflari (eland_common.classes; 7 = unknown):
  0-6 ayni; 7 road -> 2 terrain-hazard (README: simulasyonda boyle); belirsizler temkinli: 252 (cim ya da bitki) -> 2,
  253 (su ya da yol) -> 4, 254 (sert zemin ya da yol) -> 2; 255 sayilmaz -> 7.
Olcek: maske 8 cm/piksele yeniden orneklenir (en yakin komsu). Bolumler v4'unki (split sutunu).
Cikti: ~/eland_veri/rl/v4/maske/<bolum>/<ad>.png, liste <bolum>.txt (elev: yolu da yazilir; da_v4.py doldurur),
ozet.csv (sinif paylari).

    python3 hazirla.py
"""
import csv
import collections
import os

import cv2
import numpy as np

V = os.path.expanduser('~/eland_veri/v4_zip/veri_v4')
O = os.path.expanduser('~/eland_veri/rl/v4')
HUCRE = 0.08
LUT = np.full(256, 7, np.uint8)
LUT[:7] = np.arange(7)
LUT[7], LUT[252], LUT[253], LUT[254], LUT[255] = 2, 2, 4, 2, 7


def main():
    rows = list(csv.DictReader(open(f'{V}/manifest.csv')))
    listeler = collections.defaultdict(list)
    pay = collections.defaultdict(lambda: np.zeros(8))
    sayi = collections.Counter()
    for m in rows:
        if m['kaynak'] not in ('floodnet', 'messi') or not m['gsd_cm']:
            continue
        g = float(m['gsd_cm']) / 100
        sx, sy = int(m['w']) * g, int(m['h']) * g
        if sx < 60 or sy < 45:
            continue
        ad = m['id'].replace('/', '__')
        b = m['split']
        mp, ep = f'{O}/maske/{b}/{ad}.png', f'{O}/elev/{b}/{ad}.png'
        if not os.path.exists(mp):
            m8 = cv2.imread(f"{V}/{m['maske8']}", cv2.IMREAD_UNCHANGED)
            rl = cv2.resize(LUT[m8], (round(sx / HUCRE), round(sy / HUCRE)), interpolation=cv2.INTER_NEAREST)
            os.makedirs(os.path.dirname(mp), exist_ok=True)
            cv2.imwrite(mp, rl)
        else:
            rl = cv2.imread(mp, cv2.IMREAD_UNCHANGED)
        pay[(m['kaynak'], b)] += np.bincount(rl[::4, ::4].ravel(), minlength=8)[:8]
        sayi[(m['kaynak'], b)] += 1
        listeler[b].append(f'{mp} {sx:.3f} {sy:.3f} elev:{ep}\n')
    for b, v in listeler.items():
        open(f'{O}/{b}.txt', 'w').writelines(v)
    ad = ['safe-soft', 'safe-hard', 'terrain-hazard', 'structure', 'water', 'vehicle-animal', 'person', 'unknown']
    with open(f'{O}/ozet.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['kaynak', 'bolum', 'kare'] + ad)
        for k in sorted(pay):
            w.writerow([*k, sayi[k]] + [round(100 * x / pay[k].sum(), 2) for x in pay[k]])
    for k in sorted(pay):
        print(k, sayi[k], ' '.join(f'{a[:6]} {100 * x / pay[k].sum():4.1f}' for a, x in zip(ad, pay[k])))
    print({b: len(v) for b, v in listeler.items()})


if __name__ == '__main__':
    main()
