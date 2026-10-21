"""Duzeltme 24: yanal hiz 1.5 ve 2.0 m/s (c23 tarifi, 3'er tohum, 1M). docs/onkayit/rl_f0_onkayit.md. Karar H24.

    bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/hiz2/hiz2_tur.py'
"""
import json
import os
import subprocess
import sys
import time

H = os.path.expanduser('~')
sys.path.insert(0, f'{H}/rl_inis/arama')
import arama  # noqa: E402

arama.A = f'{H}/rl_inis/arama/hiz2'
arama.K = f'{H}/rl_inis/kos/hiz2'
os.makedirs(arama.A, exist_ok=True)
os.makedirs(arama.K, exist_ok=True)
C23 = {'r_step': -0.5, 'a_descend': 1.0}
CESIT = [('y15', 1.5), ('y20', 2.0)]
_degerlendirme = arama.degerlendirme_args


def degerlendirme_args(args):
    """The lateral speed changes the dynamics, so the evaluation must fly with it (evaluate.py --env-json)."""
    env = json.loads(arama.secenek(args, '--env-json') or '{}')
    out = _degerlendirme(args)
    fiz = {k: env[k] for k in ('v_lateral', 'gimbal') if k in env}   # what changes the flight, not the reward
    if fiz:
        out += ['--env-json', json.dumps(fiz)]
    if env.get('gimbal'):
        out += ['--kalkan2']        # amendment 25b is judged with the locking shield (amendment 22)
    return out


arama.degerlendirme_args = degerlendirme_args


def main():
    hazir = f'{H}/rl_inis/gimbal/hazir'           # amendment 25: AirSim + gimbal and its evaluation go first
    while not os.path.exists(hazir):
        time.sleep(60)
    arama.log('yanal hiz ve gimbal egitim turu basladi (Duzeltme 24, 25b)')
    isler = []
    for ad, v in CESIT:
        args = ['--reward', 'zemin_v1', '--env-json', json.dumps({**C23, 'v_lateral': v})]
        for t in (0, 1, 2):
            isler.append(arama.Is('Y', ad, args, t, f'{arama.K}/{ad}_s{t}', degerlendir=('val_b32', 10), tam=True))
    g_args = ['--reward', 'zemin_v1', '--env-json', json.dumps({**C23, 'gimbal': True})]   # amendment 25b
    for t in (0, 1, 2):
        isler.append(arama.Is('Y', 'g', g_args, t, f'{arama.K}/g_s{t}', degerlendir=('val_b32', 10), tam=True))
    arama.tur_kos(isler)
    print(subprocess.run(['python3', f'{H}/rl_inis/hiz2/h24_karar.py'], capture_output=True, text=True).stdout, flush=True)
    print(subprocess.run(['python3', f'{H}/rl_inis/gimbal/h25b_karar.py'], capture_output=True, text=True).stdout,
          flush=True)
    arama.log('hiz2 bitti')


if __name__ == '__main__':
    sys.exit(main())
