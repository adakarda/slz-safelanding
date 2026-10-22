"""Duzeltme 26: c13 tarifiyle gimbal'li egitim (g13), 3 tohum, 1M. docs/onkayit/rl_f0_onkayit.md. Karar H26.
25b'nin egitimleri ve Sefa icin PX4 sinamasi (px4_sina_3.sh) bitince baslar.

    env -u PYTHONPATH -u AMENT_PREFIX_PATH bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/g13/g13_tur.py'
"""
import json
import os
import subprocess
import sys
import time

H = os.path.expanduser('~')
sys.path.insert(0, f'{H}/rl_inis/arama')
import arama  # noqa: E402

arama.A = f'{H}/rl_inis/arama/g13'
arama.K = f'{H}/rl_inis/kos/g13'
os.makedirs(arama.A, exist_ok=True)
os.makedirs(arama.K, exist_ok=True)
C13 = ['--reward', 'zemin_v3', '--max-t', '30', '--diag', '--shield-train-m', '10']   # amendment 20
_degerlendirme = arama.degerlendirme_args


def degerlendirme_args(args):
    """The gimbal changes the camera, so the evaluation must fly with it; judged with the locking shield."""
    env = json.loads(arama.secenek(args, '--env-json') or '{}')
    out = _degerlendirme(args)
    if env.get('gimbal'):
        out += ['--env-json', json.dumps({'gimbal': True}), '--kalkan2']
    return out


arama.degerlendirme_args = degerlendirme_args


def bekle():
    while (subprocess.run(['pgrep', '-f', '[h]iz2_tur\\.py|[p]x4_sina_3'], stdout=subprocess.DEVNULL).returncode == 0
           or arama.egitim_sayisi() > 0):
        time.sleep(60)


def main():
    bekle()
    arama.log('g13 turu basladi (Duzeltme 26: c13 tarifi + gimbal egitim)')
    args = [*C13, '--env-json', json.dumps({'gimbal': True})]
    isler = [arama.Is('G', 'g13', args, t, f'{arama.K}/g13_s{t}', degerlendir=('val_b32', 10), tam=True)
             for t in (0, 1, 2)]
    arama.tur_kos(isler)
    print(subprocess.run(['python3', f'{H}/rl_inis/g13/h26_karar.py'], capture_output=True, text=True).stdout,
          flush=True)
    arama.log('g13 bitti')


if __name__ == '__main__':
    sys.exit(main())
