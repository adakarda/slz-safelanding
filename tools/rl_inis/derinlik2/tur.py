"""Duzeltme 27: derinlik girdisi karsilastirmasi (c13 tarifi, fotografli 133 egitim karesi, 3 kol x 3 tohum, 1M).
  A irtifa  : simdiki "duz zemin derinligi" (kamera-zemin uzakligi; pratikte irtifa)
  B yok     : derinlik kanali sifir (depth_norm_m 1e9)
  C da      : Depth Anything V2 Small goreli yukseklik (depth_mode elev, Duzeltme 7'nin haritalari)
Kod donmus kopyadan (~/rl_inis/derinlik2/kod, 0775798): baska bir oturum env.py'yi duzeltse de bu tur etkilenmez.
Ayni anda en cok 2 egitim. Sonra degerlendir.py (her deneme yeni ortam), sonra h27_karar.py.

    env -u PYTHONPATH -u AMENT_PREFIX_PATH bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/derinlik2/tur.py'
"""
import os
import subprocess
import sys
import time

H = os.path.expanduser('~')
B = f'{H}/rl_inis/derinlik2'
K = f'{H}/rl_inis/kos/derinlik2'
D = f'{H}/eland_veri/rl/messi_ds4'
PY = os.environ.get('RL_PY', f'{H}/rl_inis/venv/bin/python')
KOD = f'{B}/kod/src/eland_rl:{B}/kod/src/eland_common'
ORTAK = ['--scenes', f'{D}/train_foto.txt', '--shard', '--sora-cell', '0.25', '--steps', '1000000', '--ent-coef', '0.01',
         '--obs', 'sem_depth_sora', '--vec', 'dummy',
         '--reward', 'zemin_v3', '--max-t', '30', '--diag', '--shield-train-m', '10']      # the c13 recipe
KOLLAR = {'A_irtifa': [], 'B_yok': ['--env-json', '{"depth_norm_m": 1e9}'], 'C_da': ['--depth-mode', 'elev']}
EN_COK = 2


def log(s):
    print(f'[derinlik2] {time.strftime("%d.%m %H:%M")} {s}', flush=True)


def ortam():
    e = dict(os.environ)
    e['PYTHONPATH'] = KOD
    return e


def bos_mb():
    return int(open('/proc/meminfo').read().split('MemAvailable:')[1].split()[0]) // 1024


def main():
    isler = [(kol, t) for t in (0, 1, 2) for kol in KOLLAR]
    calisan = {}
    while isler or calisan:
        for k, p in list(calisan.items()):
            if p.poll() is not None:
                log(f'{k[0]} s{k[1]}: egitim bitti (kod {p.returncode})')
                del calisan[k]
        while isler and len(calisan) < EN_COK and bos_mb() > 5000:
            kol, t = isler.pop(0)
            out = f'{K}/{kol}_s{t}'
            if os.path.exists(f'{out}/model.zip'):
                log(f'{kol} s{t}: model var, atlandi')
                continue
            os.makedirs(out, exist_ok=True)
            cmd = [PY, '-u', '-m', 'eland_rl.train', *ORTAK, '--seed', str(t), *KOLLAR[kol], '--out', out]
            calisan[(kol, t)] = subprocess.Popen(cmd, env=ortam(), stdout=open(f'{out}/egitim.log', 'a'),
                                                 stderr=subprocess.STDOUT)
            log(f'{kol} s{t}: egitim basladi')
            time.sleep(180)               # let it reach full memory before the next check
        time.sleep(30)
    for kol in KOLLAR:
        for t in (0, 1, 2):
            out = f'{K}/{kol}_s{t}'
            if not os.path.exists(f'{out}/model.zip'):
                log(f'{kol} s{t}: model yok, hata')
                continue
            if not os.path.exists(f'{out}/deger.csv'):
                r = subprocess.run([PY, '-u', f'{B}/degerlendir.py', kol, f'{out}/model.zip', f'{out}/deger.csv'],
                                   env=ortam(), capture_output=True, text=True)
                log(f'{kol} s{t}: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]}')
    print(subprocess.run([PY, f'{B}/h27_karar.py'], capture_output=True, text=True).stdout, flush=True)
    log('derinlik2 bitti')


if __name__ == '__main__':
    sys.exit(main())
