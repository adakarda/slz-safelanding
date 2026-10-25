"""Duzeltme 28 (28b ile): v4 verisiyle yeni egitim. c13 tarifi + Depth Anything, dengeli egitim seti (730), 5 tohum,
1M adim. Kod donmus kopyadan (~/rl_inis/v4/kod). Ayni anda en cok 2 egitim. Sonra degerlendirme (yeni model 5 tohum,
kiyas: eski son aday c13 s0-s2 ve Duzeltme 27'nin C_da s0-s2), sonra h28_karar.py.

    env -u PYTHONPATH -u AMENT_PREFIX_PATH bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/v4/tur.py'
"""
import os
import subprocess
import sys
import time

H = os.path.expanduser('~')
B = f'{H}/rl_inis/v4'
K = f'{H}/rl_inis/kos/v4'
PY = os.environ.get('RL_PY', f'{H}/rl_inis/venv/bin/python')
KOD = f'{B}/kod/src/eland_rl:{B}/kod/src/eland_common'
ORTAK = ['--scenes', f'{H}/eland_veri/rl/v4/train_denge.txt', '--shard', '--sora-cell', '0.25', '--steps', '1000000',
         '--ent-coef', '0.01', '--obs', 'sem_depth_sora', '--vec', 'dummy',
         '--reward', 'zemin_v3', '--max-t', '30', '--diag', '--shield-train-m', '10',        # the c13 recipe
         '--depth-mode', 'elev']                                                           # Depth Anything (H27)
TOHUM = (0, 1, 2, 3, 4)
KIYAS = {**{f'eski_c13_s{t}': (f'{H}/rl_inis/kos/arama/{d}/model.zip', 'flat') for t, d in
            enumerate(('t2_c13_f_kayarak_kalkan', 't3_c13_f_kayarak_kalkan_s1', 't3_c13_f_kayarak_kalkan_s2'))},
         **{f'd27_C_da_s{t}': (f'{H}/rl_inis/kos/derinlik2/C_da_s{t}/model.zip', 'elev') for t in range(3)}}
EN_COK = 2


def log(s):
    print(f'[v4] {time.strftime("%d.%m %H:%M")} {s}', flush=True)


def ortam():
    e = dict(os.environ)
    e['PYTHONPATH'] = KOD
    return e


def bos_mb():
    return int(open('/proc/meminfo').read().split('MemAvailable:')[1].split()[0]) // 1024


def degerlendir(ad, model, derinlik):
    out = f'{K}/deger/{ad}.csv'
    if os.path.exists(out):
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = subprocess.run([PY, '-u', f'{B}/degerlendir.py', derinlik, model, out], env=ortam(), capture_output=True,
                       text=True)
    log(f'{ad}: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:]}')


def main():
    isler = list(TOHUM)
    calisan = {}
    while isler or calisan:
        for t, p in list(calisan.items()):
            if p.poll() is not None:
                log(f'v4_da s{t}: egitim bitti (kod {p.returncode})')
                del calisan[t]
        while isler and len(calisan) < EN_COK and bos_mb() > 6000:
            t = isler.pop(0)
            out = f'{K}/v4_da_s{t}'
            if os.path.exists(f'{out}/model.zip'):
                log(f'v4_da s{t}: model var, atlandi')
                continue
            os.makedirs(out, exist_ok=True)
            calisan[t] = subprocess.Popen([PY, '-u', '-m', 'eland_rl.train', *ORTAK, '--seed', str(t), '--out', out],
                                          env=ortam(), stdout=open(f'{out}/egitim.log', 'a'), stderr=subprocess.STDOUT)
            log(f'v4_da s{t}: egitim basladi')
            time.sleep(300)               # scene loading and the first rollout before the next memory check
        time.sleep(30)
    for t in TOHUM:
        m = f'{K}/v4_da_s{t}/model.zip'
        if os.path.exists(m):
            degerlendir(f'v4_da_s{t}', m, 'elev')
        else:
            log(f'v4_da s{t}: model yok, hata')
    for ad, (m, d) in KIYAS.items():
        degerlendir(ad, m, d)
    print(subprocess.run([PY, f'{B}/h28_karar.py'], capture_output=True, text=True).stdout, flush=True)
    log('v4 bitti')


if __name__ == '__main__':
    sys.exit(main())
