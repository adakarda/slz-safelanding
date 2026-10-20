"""Duzeltme 15, H15 karar kurali (on kayitli): taramanin Tur 3'unde ortalama skoru en yuksek ayar, B1 ile (val_b32).

    python3 kararla.py

Skor S = B_K + 0.5 B_RL - 4 max(0, T_K - 12). Kazanan ayar yeni en iyi sayilir, eger:
  H15a  ortalama S >= B1'in ortalama S'si + 5, ve tohum ciftlerinin en az 2'sinde S >= B1-sN + 5
  H15b  ortalama B_K >= B1'inki - 3
  H15c  ortalama T_K <= 13.5 s (paper 11.8 s; B1 ~16.6 s)
  H15d  ortalama kalkansiz guvensiz <= B1'inki + 5
"""
import csv
import glob
import os
import statistics as st

H = os.path.expanduser('~')
K = f'{H}/rl_inis/kos'


def olc(yol):
    rs = list(csv.DictReader(open(yol)))
    m = {}
    for y in ('rl', 'rl_kalkan'):
        s = [r for r in rs if r['method'] == y]
        ok = [float(r['t']) for r in s if r['zemin_success'] == '1']
        m[y] = dict(B=100 * len(ok) / len(s), T=st.mean(ok) if ok else 30.0,
                    U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in s) / len(s))
    m['S'] = m['rl_kalkan']['B'] + 0.5 * m['rl']['B'] - 4 * max(0.0, m['rl_kalkan']['T'] - 12.0)
    return m


def main():
    b1 = [olc(f'{K}/b_B1_s{t}/eval_val.csv') for t in (0, 1, 2)]
    ayarlar = {}
    for yol in glob.glob(f'{K}/arama/t2_*/eval_val_b32_10.csv') + glob.glob(f'{K}/arama/t3_*_s[12]/eval_val_b32_10.csv'):
        d = os.path.basename(os.path.dirname(yol))
        if d.startswith('t2_'):
            ad, t = d[3:], 0
        else:
            ad, t = d[3:].rsplit('_s', 1)
            t = int(t)
        ayarlar.setdefault(ad, {})[t] = olc(yol)
    ort = lambda ms, f: st.mean(f(m) for m in ms)  # noqa: E731
    print(f'B1: S {ort(b1, lambda m: m["S"]):.1f}, kalkan B {ort(b1, lambda m: m["rl_kalkan"]["B"]):.1f}, '
          f'kalkan T {ort(b1, lambda m: m["rl_kalkan"]["T"]):.1f} s, RL B {ort(b1, lambda m: m["rl"]["B"]):.1f}, '
          f'RL guvensiz {ort(b1, lambda m: m["rl"]["U"]):.1f}')
    tam = {ad: v for ad, v in ayarlar.items() if len(v) == 3}
    for ad, v in sorted(tam.items(), key=lambda kv: -ort(kv[1].values(), lambda m: m['S'])):
        ms = [v[t] for t in (0, 1, 2)]
        print(f'{ad}: S {ort(ms, lambda m: m["S"]):.1f} {[round(m["S"], 1) for m in ms]}, kalkan B {ort(ms, lambda m: m["rl_kalkan"]["B"]):.1f}, '
              f'kalkan T {ort(ms, lambda m: m["rl_kalkan"]["T"]):.1f} s, RL B {ort(ms, lambda m: m["rl"]["B"]):.1f}, '
              f'RL T {ort(ms, lambda m: m["rl"]["T"]):.1f} s, RL guvensiz {ort(ms, lambda m: m["rl"]["U"]):.1f}')
    if not tam:
        print('Tur 3 tamamlanmadi; karar yok')
    else:
        ad, v = max(tam.items(), key=lambda kv: ort(kv[1].values(), lambda m: m['S']))
        ms = [v[t] for t in (0, 1, 2)]
        a_t = [ms[t]['S'] >= b1[t]['S'] + 5 for t in (0, 1, 2)]
        h_a = ort(ms, lambda m: m['S']) >= ort(b1, lambda m: m['S']) + 5 and sum(a_t) >= 2
        h_b = ort(ms, lambda m: m['rl_kalkan']['B']) >= ort(b1, lambda m: m['rl_kalkan']['B']) - 3
        h_c = ort(ms, lambda m: m['rl_kalkan']['T']) <= 13.5
        h_d = ort(ms, lambda m: m['rl']['U']) <= ort(b1, lambda m: m['rl']['U']) + 5
        print(f'kazanan aday {ad}: H15a {h_a} (tohum {a_t}) | H15b {h_b} | H15c {h_c} | H15d {h_d}')
        print(f'KARAR: {ad} {"yeni en iyi ayar" if h_a and h_b and h_c and h_d else "B1/B2-s0 yerini almaz"}')


if __name__ == "__main__":
    main()
