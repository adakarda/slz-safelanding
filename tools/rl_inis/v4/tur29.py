"""Duzeltme 29 sirasi: (1) eksik hucre "yeni veri + irtifa" (v4_flat, c13 tarifi, train_denge, 5 tohum, tek tek);
(2) ayni anda, var olan 11 modelin tam karsilastirmasi (faktor.py, en cok 2 paralel); (3) v4_flat modelleri bitince
onlarin karsilastirmasi; (4) h29_ozet.py. Donmus kod. Ara kayittan devam eder.

    env -u PYTHONPATH -u AMENT_PREFIX_PATH bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/v4/tur29.py'
"""
import glob
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
         '--reward', 'zemin_v3', '--max-t', '30', '--diag', '--shield-train-m', '10']       # flat depth: no --depth-mode
TOHUM = (0, 1, 2, 3, 4)
MODELLER = {**{f'eski_c13_s{t}': (f'{H}/rl_inis/kos/arama/{d}/model.zip', 'flat') for t, d in
               enumerate(('t2_c13_f_kayarak_kalkan', 't3_c13_f_kayarak_kalkan_s1', 't3_c13_f_kayarak_kalkan_s2'))},
            **{f'eski_da_s{t}': (f'{H}/rl_inis/kos/derinlik2/C_da_s{t}/model.zip', 'elev') for t in range(3)},
            **{f'yeni_da_s{t}': (f'{K}/v4_da_s{t}/model.zip', 'elev') for t in TOHUM},
            **{f'yeni_irtifa_s{t}': (f'{K}/v4_flat_s{t}/model.zip', 'flat') for t in TOHUM}}


def log(s):
    print(f'[d29] {time.strftime("%d.%m %H:%M")} {s}', flush=True)


def ortam():
    e = dict(os.environ)
    e['PYTHONPATH'] = KOD
    return e


def main():
    egitim = [t for t in TOHUM if not os.path.exists(f'{K}/v4_flat_s{t}/model.zip')]
    tr = None
    ev = {}
    os.makedirs(f'{K}/faktor', exist_ok=True)
    while True:
        if tr and tr[1].poll() is not None:
            log(f'v4_flat s{tr[0]}: egitim bitti (kod {tr[1].returncode})')
            tr = None
        if tr is None and egitim:
            t = egitim.pop(0)
            out = f'{K}/v4_flat_s{t}'
            os.makedirs(out, exist_ok=True)
            ck = sorted(glob.glob(f'{out}/ckpt/model_*_steps.zip'), key=lambda c: int(c.split('_')[-2]))
            devam = ['--resume', ck[-1]] if ck else []
            tr = (t, subprocess.Popen([PY, '-u', '-m', 'eland_rl.train', *ORTAK, '--seed', str(t), *devam, '--out', out],
                                      env=ortam(), stdout=open(f'{out}/egitim.log', 'a'), stderr=subprocess.STDOUT))
            log(f'v4_flat s{t}: egitim basladi {devam[1:] or ""}')
        for ad, p in list(ev.items()):
            if p.poll() is not None:
                o = open(f'{K}/faktor/{ad}.log').read().strip().splitlines()
                log(f'{ad}: {o[-1] if o else "cikti yok"}')
                del ev[ad]
        bekleyen = [ad for ad, (m, d) in MODELLER.items() if os.path.exists(m)
                    and not os.path.exists(f'{K}/faktor/{ad}.csv') and ad not in ev]
        while bekleyen and len(ev) < 2:
            ad = bekleyen.pop(0)
            m, d = MODELLER[ad]
            ev[ad] = subprocess.Popen([PY, '-u', f'{B}/faktor.py', d, m, f'{K}/faktor/{ad}.csv'], env=ortam(),
                                      stdout=open(f'{K}/faktor/{ad}.log', 'w'), stderr=subprocess.STDOUT)
            log(f'{ad}: karsilastirma basladi')
        if tr is None and not egitim and not ev and all(os.path.exists(f'{K}/faktor/{ad}.csv') for ad in MODELLER):
            break
        time.sleep(30)
    print(subprocess.run([PY, f'{B}/h29_ozet.py'], capture_output=True, text=True).stdout, flush=True)
    log('d29 bitti')


if __name__ == '__main__':
    sys.exit(main())
