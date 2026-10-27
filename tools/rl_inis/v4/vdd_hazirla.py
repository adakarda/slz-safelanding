"""Duzeltme 31: VDD sahneleri RL'ye (Arda, 27.10: "VDD tahmini olcekle", TU Graz disarida, FloodNet dengeli).

- Olcek: irtifa yok; v4 segmentasyon egitimindeki VDD araliginin (1.8-4.3 cm/px) ortasi 3.0 cm/px kabul edilir.
  4000 x 3000 goruntu -> 120 x 90 m.
- Siniflar: VDD'de inilebilir sinif yok; "vegetation" (masks8 = 252: cim ya da bitki) tek etiket. Bu piksellerde v4
  segmentasyon modelinin tahmini kullanilir: cim (0) ise 0, aksi hepsi 2 (temkinli). Oteki etiketler VDD'nin kendisi:
  yol -> 2, 253 -> 4, 254 -> 2, 255 -> 7 (hazirla.py ile ayni).
- Not: v4, VDD egitim bolumunu gordu; dogrulama bolumunu gormedi.
Cikti: ~/eland_veri/rl/v4/maske/{train,val}/vdd__*.png, train_vdd.txt, val_vdd.txt, train_hepsi.txt (train_denge + VDD).

    ~/v3_test/venv/bin/python vdd_hazirla.py
"""
import csv
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, '/home/arda/v3_test/model')
import v3_model as M  # noqa: E402

V = os.path.expanduser('~/eland_veri/v4_zip/veri_v4')
O = os.path.expanduser('~/eland_veri/rl/v4')
GSD = 3.0
HUCRE = 0.08
LUT = np.full(256, 7, np.uint8)
LUT[:7] = np.arange(7)
LUT[7], LUT[252], LUT[253], LUT[254], LUT[255] = 2, 2, 4, 2, 7


def main():
    model = M.yukle('/home/arda/v4_seg/best_v4.pth')
    rows = [m for m in csv.DictReader(open(f'{V}/manifest.csv')) if m['kaynak'] == 'vdd' and m['split'] in ('train', 'val')]
    liste = {'train': [], 'val': []}
    pay = {'train': np.zeros(8), 'val': np.zeros(8)}
    for m in rows:
        b = m['split']
        ad = m['id'].replace('/', '__')
        ad = ad if ad.startswith('vdd') else 'vdd__' + ad
        mp, ep = f'{O}/maske/{b}/{ad}.png', f'{O}/elev/{b}/{ad}.png'
        sx, sy = int(m['w']) * GSD / 100, int(m['h']) * GSD / 100
        if not os.path.exists(mp):
            m8 = cv2.imread(f"{V}/{m['maske8']}", cv2.IMREAD_UNCHANGED)
            bgr = cv2.imread(f"{V}/{m['goruntu']}")
            p = M.segmentle(model, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), gsd_cm=GSD, sim_siniflari=False)
            rl = LUT[m8]
            veg = m8 == 252
            rl[veg & (p == 0)] = 0
            os.makedirs(os.path.dirname(mp), exist_ok=True)
            cv2.imwrite(mp, cv2.resize(rl, (round(sx / HUCRE), round(sy / HUCRE)), interpolation=cv2.INTER_NEAREST))
        rl = cv2.imread(mp, cv2.IMREAD_UNCHANGED)
        pay[b] += np.bincount(rl[::4, ::4].ravel(), minlength=8)[:8]
        liste[b].append(f'{mp} {sx:.3f} {sy:.3f} elev:{ep}\n')
    open(f'{O}/train_vdd.txt', 'w').writelines(liste['train'])
    open(f'{O}/val_vdd.txt', 'w').writelines(liste['val'])
    open(f'{O}/train_hepsi.txt', 'w').writelines(open(f'{O}/train_denge.txt').readlines() + liste['train'])
    ad = ['cim', 'sert', 'bitki+yol', 'yapi', 'su', 'arac', 'insan', 'bilinmiyor']
    for b in pay:
        print(b, len(liste[b]), ' '.join(f'{a} {100 * x / pay[b].sum():.1f}' for a, x in zip(ad, pay[b])))


if __name__ == '__main__':
    main()
