"""Duzeltme 19: B2-s0'i hizlandirma (ince ayar). docs/onkayit/rl_f0_onkayit.md. Tarama bitince, gozlem turundan once.

B2-s0'in 1M modelinden, B2'nin ayarlariyla (zemin_v1 + aynalama) ve hiz oduluyle +500k adim (--resume, --steps 1.5M;
ogrenme orani 1e-4'ten 0'a). Uc cesit, val_b32 x 10 tam degerlendirme; karar H19 (b2hiz_karar.py). Tek tohum.

  h1_hiz          + adim -0.5, alcal +1 (90 s)
  h2_hiz_45s      + hiz odulu, egitimde 45 s
  h3_hiz_kalkan   + hiz odulu, kalkan egitimde (10 m)

    bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/arama/b2hiz_tur.py'
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arama  # noqa: E402

H = os.path.expanduser('~')
AR = f'{H}/rl_inis/arama'
arama.A = f'{AR}/b2hiz'
arama.K = f'{H}/rl_inis/kos/b2hiz'
os.makedirs(arama.A, exist_ok=True)
os.makedirs(arama.K, exist_ok=True)
B2 = f'{H}/rl_inis/kos/b_B2_s0/model.zip'
TABAN = ['--reward', 'zemin_v1', '--mirror', '--steps', '1500000']
HIZ = '{"r_step": -0.5, "a_descend": 1.0}'
CESIT = [('h1_hiz', TABAN + ['--env-json', HIZ]),
         ('h2_hiz_45s', TABAN + ['--env-json', HIZ, '--max-t', '45']),
         ('h3_hiz_kalkan', TABAN + ['--env-json', HIZ, '--shield-train-m', '10'])]


def main():
    while not (os.path.exists(f'{AR}/arama.log') and 'arama bitti' in open(f'{AR}/arama.log').read()):
        time.sleep(300)
    try:
        arama.log('B2-s0 hizlandirma basladi (ince ayar, +500k)')
        isler = [arama.Is('H', c, a, 0, f'{arama.K}/{c}', resume=B2, degerlendir=('val_b32', 10), tam=True)
                 for c, a in CESIT]
        arama.tur_kos(isler)
        print(arama.sh(f'python3 {AR}/b2hiz_karar.py'), flush=True)
    finally:
        arama.log('b2hiz bitti')


if __name__ == '__main__':
    sys.exit(main())
