"""Duzeltme 21, H21 karar kurali (on kayitli): yedek inis (eland_rl.yedek), ayni modelin kalkanli RL'siyle, ayni 320
deneme (val_b32 x 10). Esli kiyas: degerlendirme deterministik, eski CSV'nin rl_kalkan satirlari ayni baslangiclar.

  Birincil ayarlar: c13 ve c23 (taramanin Tur 3'u, 3'er tohum). Her ayar icin, tohum basina
    dB = B(rl_kalkan_yedek) - B(rl_kalkan),  dU = U(rl_kalkan_yedek) - U(rl_kalkan)   (yuzde puan)
  H21a  ortalama dB >= +3, ve tohumlarin en az 2'sinde dB >= +3
  H21b  ortalama dU <= +2
  Yedek inis benimsenir, eger H21a ve H21b c13'te VE c23'te tutarsa.
  Tanimlayici: sure, skor, sure asimlarinin neye donustugu, kalkansiz (rl_yedek), B2-s0.

    python3 h21_karar.py
"""
import csv
import os
import statistics as st

H = os.path.expanduser('~')
K = f'{H}/rl_inis/kos'
Y = f'{H}/rl_inis/kos/yedek'
AYARLAR = {
    'c13': [f'{K}/arama/t2_c13_f_kayarak_kalkan', f'{K}/arama/t3_c13_f_kayarak_kalkan_s1',
            f'{K}/arama/t3_c13_f_kayarak_kalkan_s2'],
    'c23': [f'{K}/arama/t2_c23_b1_adim05_alcal1', f'{K}/arama/t3_c23_b1_adim05_alcal1_s1',
            f'{K}/arama/t3_c23_b1_adim05_alcal1_s2'],
    'B2': [f'{K}/b_B2_s0'],
}


def eski_csv(d):
    p = f'{d}/eval_val_b32_10.csv'
    return p if os.path.exists(p) else f'{d}/eval_val.csv'


def satirlar(p, yontem):
    return {(r['scene'], r['start']): r for r in csv.DictReader(open(p)) if r['method'] == yontem}


def olc(rs):
    n = len(rs)
    ok = [float(r['t']) for r in rs if r['zemin_success'] == '1']
    return dict(B=100 * len(ok) / n, T=st.mean(ok) if ok else 30.0,
                U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in rs) / n,
                TO=100 * sum(r['outcome'] == 'timeout' for r in rs) / n)


def skor(bk, brl, tk):
    return bk + 0.5 * brl - 4 * max(0.0, tk - 12.0)


def main():
    kabul = {}
    for ayar, dizinler in AYARLAR.items():
        dB, dU = [], []
        print(f'== {ayar}')
        for d in dizinler:
            ad = os.path.basename(d)
            yeni = f'{Y}/{ad}.csv'
            if not os.path.exists(yeni):
                print(f'  {ad}: degerlendirme yok')
                continue
            e_rl, e_k = satirlar(eski_csv(d), 'rl'), satirlar(eski_csv(d), 'rl_kalkan')
            y_rl, y_k = satirlar(yeni, 'rl_yedek'), satirlar(yeni, 'rl_kalkan_yedek')
            assert set(e_k) == set(y_k), ad
            a, b = olc(list(e_k.values())), olc(list(y_k.values()))
            ar, br = olc(list(e_rl.values())), olc(list(y_rl.values()))
            dB.append(b['B'] - a['B'])
            dU.append(b['U'] - a['U'])
            donusum = {}
            for k in e_k:
                if e_k[k]['outcome'] == 'timeout':
                    yeni_s = 'basari' if y_k[k]['zemin_success'] == '1' else y_k[k]['outcome']
                    donusum[yeni_s] = donusum.get(yeni_s, 0) + 1
            print(f'  {ad}: kalkanli B {a["B"]:.1f} -> {b["B"]:.1f} | U {a["U"]:.1f} -> {b["U"]:.1f} | '
                  f'TO {a["TO"]:.1f} -> {b["TO"]:.1f} | T {a["T"]:.1f} -> {b["T"]:.1f} s | '
                  f'S {skor(a["B"], ar["B"], a["T"]):.1f} -> {skor(b["B"], br["B"], b["T"]):.1f} | '
                  f'kalkansiz B {ar["B"]:.1f} -> {br["B"]:.1f}, U {ar["U"]:.1f} -> {br["U"]:.1f} | '
                  f'sure asimlari -> {donusum}')
        if ayar == 'B2' or len(dB) < 3:
            continue
        h_a = st.mean(dB) >= 3 and sum(x >= 3 for x in dB) >= 2
        h_b = st.mean(dU) <= 2
        kabul[ayar] = h_a and h_b
        print(f'  ortalama dB {st.mean(dB):+.1f} {[round(x, 1) for x in dB]} | dU {st.mean(dU):+.1f} | '
              f'H21a {h_a} | H21b {h_b}')
    if len(kabul) < 2:
        print('KARAR: degerlendirmeler eksik')
    else:
        print('KARAR: yedek inis ' + ('benimsenir' if all(kabul.values()) else 'benimsenmez') + f' {kabul}')


if __name__ == '__main__':
    main()
