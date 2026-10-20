"""Duzeltme 15: odul ve egitim ayarlari taramasi (docs/onkayit/rl_f0_onkayit.md). On kayitli turlar:

  Tur 1  konfig_t1.json'daki her ayar: tohum 0, 400k adim (ogrenme orani 1M programinda, --stop-at),
         val_b64 x 5 baslangic = 320 deneme, yalniz RL ve RL + kalkan.
  Tur 2  Tur 1'in skoru en yuksek 4 ayari: ayni kosu 1M'ye tamamlanir (--resume), val_b64 x 10 = 640 deneme.
  Tur 3  Tur 2'nin skoru en yuksek 2 ayari: tohum 1 ve 2 sifirdan 1M; uc tohum val_b32 x 10 = 320 deneme
         (tam degerlendirme, kahin dahil). Karar H15 (kararla.py).

Skor  S = B_K + 0.5 * B_RL - 4 * max(0, T_K - 12)
      B_K: RL + kalkan zemin basarisi (%), B_RL: kalkansiz (%), T_K: RL + kalkanin basarili inis suresi (s).
      Egitimde kalkan olan ayarlar degerlendirmede de kalkanla kosar (ortam icinde).

Yer kurali: ayni anda en fazla 2 egitim, en az 7 GB bos bellek, AirSim acikken baslamaz; F kuyrugu uc tohumunu
baslatmadan baslamaz; F bitip havada_sonra.sh beklerken yeni egitim baslatmaz (AirSim denemesi once).

    bash -c 'source ~/rl_inis/ortam.sh; exec $RL_PY -u ~/rl_inis/arama/arama.py'
"""
import csv
import json
import os
import statistics as st
import subprocess
import sys
import time

H = os.path.expanduser('~')
A = f'{H}/rl_inis/arama'
K = f'{H}/rl_inis/kos/arama'
D = f'{H}/eland_veri/rl/messi_ds4'
PY = os.environ.get('RL_PY', f'{H}/rl_inis/venv/bin/python')
ORTAK = ['--scenes', f'{D}/train_b.txt', '--shard', '--sora-cell', '0.25', '--steps', '1000000', '--ent-coef', '0.01',
         '--obs', 'sem_depth_sora', '--vec', 'dummy']
DUMAN = os.environ.get('ARAMA_DUMAN') == '1'    # smoke test of this script: tiny runs in /tmp, no decision value
if DUMAN:
    A, K = '/tmp/arama_duman', '/tmp/arama_duman/kos'
    ORTAK[1] = f'{D}/val_b32.txt'
    os.makedirs(A, exist_ok=True)
os.makedirs(K, exist_ok=True)


def log(msg):
    line = f'[arama] {time.strftime("%d.%m %H:%M")} {msg}'
    print(line, flush=True)
    with open(f'{A}/arama.log', 'a') as f:
        f.write(line + '\n')


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def egitim_sayisi():
    return int(sh("pgrep -fc '[e]land_rl\\.train'") or 0)


def bos_mb():
    return int(sh("free -m | awk 'NR==2 {print $7}'") or 0)


# Trainings at once. The observation-channel rounds set 1: with --kanallar a run peaks at ~6.5 GB RSS + 2 GB swap;
# two of them filled WSL's 12 GB and the distro restarted (2026-10-20 19:31, yurutme notu in rl_f0_onkayit.md).
EN_COK = 2


def yer_var():
    if DUMAN:
        return bos_mb() > 1500
    if egitim_sayisi() >= EN_COK or bos_mb() < 7000:
        return False
    if sh("pgrep -f '[r]un_airsim\\.sh|[i]nis_sina\\.sh'"):
        return False
    kos = f'{H}/rl_inis/kos'
    if not os.path.exists(f'{kos}/f_F1_s2/args.json'):
        return False            # the F queue still has seeds to launch: no race for its slots
    once_airsim = not any(os.path.exists(f'{kos}/{x}_CALISIYOR') for x in ('D', 'E', 'F'))
    if once_airsim and sh("pgrep -f '[h]avada_sonra\\.sh'"):
        return False            # the air-start test runs first, once nothing else trains
    return True


def secenek(args, ad):
    i = args.index(ad) if ad in args else -1
    return args[i + 1] if i >= 0 else None


def degerlendirme_args(args):
    out = ['--reward', secenek(args, '--reward') or 'zemin_v1', '--obs', 'sem_depth_sora', '--sora-cell', '0.25']
    if '--diag' in args:
        out.append('--diag')
    if secenek(args, '--shield-train-m'):
        out += ['--shield-train-m', secenek(args, '--shield-train-m')]
    if secenek(args, '--kanallar'):                       # amendment 16
        out += ['--kanallar', secenek(args, '--kanallar')]
    return out


def olc(csv_yol):
    rs = list(csv.DictReader(open(csv_yol)))
    m = {}
    for y in ('rl', 'rl_kalkan'):
        s = [r for r in rs if r['method'] == y]
        n = len(s)
        ok = [float(r['t']) for r in s if r['zemin_success'] == '1']
        m[y] = dict(B=100 * len(ok) / n, T=st.mean(ok) if ok else 30.0,
                    U=100 * sum(r['outcome'] != 'timeout' and r['zemin_success'] != '1' for r in s) / n,
                    TO=100 * sum(r['outcome'] == 'timeout' for r in s) / n,
                    Y=100 * sum(r['soft'] == '1' for r in s) / n, n=n)
    m['S'] = m['rl_kalkan']['B'] + 0.5 * m['rl']['B'] - 4 * max(0.0, m['rl_kalkan']['T'] - 12.0)
    return m


class Is:
    """One training (optional) followed by one evaluation."""

    def __init__(self, tur, ad, args, tohum, out, stop_at=0, resume='', degerlendir=('val_b64', 5), tam=False):
        self.tur, self.ad, self.args, self.tohum, self.out = tur, ad, args, tohum, out
        self.stop_at, self.resume, self.deg, self.tam = stop_at, resume, degerlendir, tam
        self.proc, self.faz = None, 'bekliyor'
        self.eval_csv = os.path.join(out, f'eval_{degerlendir[0]}_{degerlendir[1]}.csv')
        self.hedef_model = os.path.join(out, 'model.zip')

    def egitim_bitti(self):
        return os.path.exists(self.hedef_model) and os.path.exists(os.path.join(self.out, 'BITTI'))

    def baslat_egitim(self):
        os.makedirs(self.out, exist_ok=True)
        cmd = [PY, '-u', '-m', 'eland_rl.train', *ORTAK, '--seed', str(self.tohum), *self.args, '--out', self.out]
        if self.stop_at:
            cmd += ['--stop-at', str(self.stop_at)]
        if self.resume:
            cmd += ['--resume', self.resume]
        ck = sorted(os.listdir(os.path.join(self.out, 'ckpt'))) if os.path.isdir(os.path.join(self.out, 'ckpt')) else []
        if not self.resume and ck:      # carry on after a crash or a sleep from the last checkpoint
            son = max(ck, key=lambda f: int(f.split('_')[1]))
            if int(son.split('_')[1]) < (self.stop_at or 1_000_000):
                cmd += ['--resume', os.path.join(self.out, 'ckpt', son)]
        self.proc = subprocess.Popen(cmd, stdout=open(os.path.join(self.out, 'egitim.log'), 'a'), stderr=subprocess.STDOUT)
        self.faz = 'egitim'
        log(f'tur {self.tur} {self.ad} s{self.tohum}: egitim basladi ({" ".join(self.args)})')

    def baslat_degerlendirme(self):
        liste, bas = self.deg
        cmd = [PY, '-u', '-m', 'eland_rl.evaluate', '--scenes', f'{D}/{liste}.txt', '--model', self.hedef_model,
               '--starts', str(bas), *degerlendirme_args(self.args), '--out', self.eval_csv]
        if not self.tam:
            cmd.append('--only-rl')
        else:
            cmd.append('--oracle')
        self.proc = subprocess.Popen(cmd, stdout=open(self.eval_csv[:-4] + '.txt', 'w'), stderr=subprocess.STDOUT)
        self.faz = 'degerlendirme'

    def ilerle(self):
        """Advance; returns True when this job is finished."""
        if self.faz == 'bitti':
            return True
        if self.proc is not None and self.proc.poll() is None:
            return False
        if self.faz == 'degerlendirme' and not os.path.exists(self.eval_csv):
            self.deneme = getattr(self, 'deneme', 0) + 1
            log(f'tur {self.tur} {self.ad} s{self.tohum}: degerlendirme hata {self.proc.returncode} (deneme {self.deneme})')
            if self.deneme <= 2:
                self.baslat_degerlendirme()
            else:
                self.faz = 'bitti'
                self.sonuc = {'S': -999.0, 'rl': dict(B=0, T=30, U=0, TO=0, Y=0, n=0),
                              'rl_kalkan': dict(B=0, T=30, U=0, TO=0, Y=0, n=0)}
                return True
            return False
        if self.faz == 'egitim':
            if self.proc.returncode == 0:
                open(os.path.join(self.out, 'BITTI'), 'w').close()
            else:
                log(f'tur {self.tur} {self.ad} s{self.tohum}: egitim hata {self.proc.returncode}; yeniden denenecek')
                self.faz, self.proc = 'bekliyor', None
                return False
        if self.faz in ('egitim', 'bekliyor') and self.egitim_bitti() and not os.path.exists(self.eval_csv):
            self.baslat_degerlendirme()
            return False
        if os.path.exists(self.eval_csv) and self.egitim_bitti():
            if self.faz != 'bitti':
                self.sonuc = olc(self.eval_csv)
                k, r = self.sonuc['rl_kalkan'], self.sonuc['rl']
                log(f'tur {self.tur} {self.ad} s{self.tohum}: S {self.sonuc["S"]:.1f} | kalkan B {k["B"]:.1f} T {k["T"]:.1f} s '
                    f'| RL B {r["B"]:.1f} T {r["T"]:.1f} s U {r["U"]:.1f} TO {r["TO"]:.1f}')
                self.faz = 'bitti'
                ozet_yaz()
            return True
        return False

    def egitim_gerek(self):
        return not self.egitim_bitti()


TUM = []


def ozet_yaz():
    satir = ['| tur | ayar | tohum | S | kalkan B | kalkan T (s) | RL B | RL T (s) | RL guvensiz | RL sure doldu | cim |',
             '|---|---|---|---|---|---|---|---|---|---|---|']
    for j in sorted([j for j in TUM if j.faz == 'bitti'], key=lambda j: (j.tur, -j.sonuc['S'])):
        k, r = j.sonuc['rl_kalkan'], j.sonuc['rl']
        satir.append(f'| {j.tur} | {j.ad} | {j.tohum} | {j.sonuc["S"]:.1f} | {k["B"]:.1f} | {k["T"]:.1f} | {r["B"]:.1f} | '
                     f'{r["T"]:.1f} | {r["U"]:.1f} | {r["TO"]:.1f} | {r["Y"]:.1f} |')
    open(f'{A}/ozet.md', 'w').write('\n'.join(satir) + '\n')


def tur_kos(isler):
    TUM.extend(isler)
    bekleyen = list(isler)
    while True:
        biten = [j for j in isler if j.ilerle()]
        if len(biten) == len(isler):
            return
        for j in [j for j in bekleyen if j.faz == 'bekliyor']:
            if not j.egitim_gerek():
                bekleyen.remove(j)
                j.ilerle()
                continue
            if yer_var():
                j.baslat_egitim()
                bekleyen.remove(j)
                time.sleep(180)         # let it take its memory before measuring again
            break
        for j in isler:                 # a failed training goes back to the queue
            if j.faz == 'bekliyor' and j not in bekleyen and j.egitim_gerek():
                bekleyen.append(j)
        time.sleep(30)


def referans():
    """Scale on val_b64 for the screening (no decision): B1-s0, B2-s0 and, once there, D1-s0 and F1-s0."""
    for ad in ('b_B1_s0', 'b_B2_s0', 'd_D1_s0'):
        m = f'{H}/rl_inis/kos/{ad}/model.zip'
        out = f'{K}/ref_{ad}'
        csv_yol = f'{out}/eval_val_b64_5.csv'
        if os.path.exists(m) and not os.path.exists(csv_yol):
            os.makedirs(out, exist_ok=True)
            odul = json.load(open(f'{H}/rl_inis/kos/{ad}/args.json'))['reward']
            subprocess.run([PY, '-u', '-m', 'eland_rl.evaluate', '--scenes', f'{D}/val_b64.txt', '--model', m, '--starts', '5',
                            '--reward', odul, '--obs', 'sem_depth_sora', '--sora-cell', '0.25', '--only-rl', '--out', csv_yol],
                           stdout=open(csv_yol[:-4] + '.txt', 'w'), stderr=subprocess.STDOUT)
        if os.path.exists(csv_yol):
            s = olc(csv_yol)
            log(f'referans {ad} (val_b64 x 5): S {s["S"]:.1f} | kalkan B {s["rl_kalkan"]["B"]:.1f} T {s["rl_kalkan"]["T"]:.1f} s'
                f' | RL B {s["rl"]["B"]:.1f} T {s["rl"]["T"]:.1f} s U {s["rl"]["U"]:.1f}')


def mevcut_hazirla(konf):
    """Amendment 15c: a config an earlier experiment already trained with the same settings (seed 0 = Tur 1 and 2,
    seeds 1 and 2 = Tur 3) is not trained again: its 400k checkpoint is the Tur 1 model (same 1M LR schedule), its
    1M model the Tur 2 model, its seed 1 and 2 models the Tur 3 seeds. Called before every round, so a seed that
    finished in the meantime is picked up."""
    import shutil
    kos = f'{H}/rl_inis/kos'
    for c in konf:
        desen = c.get('mevcut')
        if not desen:
            continue
        for hedef, kosu, dosya in ((f'{K}/t1_{c["ad"]}', desen.format(0), 'ckpt/model_400000_steps.zip'),
                                   (f'{K}/t2_{c["ad"]}', desen.format(0), 'model.zip'),
                                   (f'{K}/t3_{c["ad"]}_s1', desen.format(1), 'model.zip'),
                                   (f'{K}/t3_{c["ad"]}_s2', desen.format(2), 'model.zip')):
            kaynak = f'{kos}/{kosu}/{dosya}'
            if os.path.exists(kaynak) and not os.path.exists(f'{hedef}/BITTI'):
                if os.path.isdir(f'{hedef}/ckpt'):
                    shutil.rmtree(f'{hedef}/ckpt')            # a run started before amendment 15c: not used
                os.makedirs(hedef, exist_ok=True)
                shutil.copy(kaynak, f'{hedef}/model.zip')
                shutil.copy(f'{kos}/{kosu}/args.json', f'{hedef}/args.json')
                open(f'{hedef}/MEVCUT', 'w').write(kaynak + '\n')
                open(f'{hedef}/BITTI', 'w').close()
                log(f'{c["ad"]}: {os.path.basename(hedef)} <- mevcut {kosu}/{dosya}')


def main():
    konf = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'konfig_t1.json')))
    mevcut_hazirla(konf)
    if DUMAN:
        konf = [konf[2], konf[13]]      # sliding descents and the in-training shield: the riskiest paths
        Is.__init__.__defaults__ = (0, '', ('val_b64', 1), False)
    log(f'basladi: tur 1, {len(konf)} ayar')
    if not DUMAN:
        referans()
    t1 = [Is(1, c['ad'], c['args'], 0, f'{K}/t1_{c["ad"]}', stop_at=4096 if DUMAN else 400_000) for c in konf]
    if DUMAN:
        tur_kos(t1)
        log('duman bitti: ' + ', '.join(f'{j.ad} S {j.sonuc["S"]:.1f}' for j in t1))
        return
    tur_kos(t1)
    sira = sorted(t1, key=lambda j: -j.sonuc['S'])
    log('tur 1 bitti; sira: ' + ', '.join(f'{j.ad} {j.sonuc["S"]:.1f}' for j in sira))
    mevcut_hazirla(konf)
    t2 = [Is(2, j.ad, j.args, 0, f'{K}/t2_{j.ad}', resume=f'{j.out}/model.zip', degerlendir=('val_b64', 10))
          for j in sira[:4]]
    tur_kos(t2)
    sira2 = sorted(t2, key=lambda j: -j.sonuc['S'])
    log('tur 2 bitti; sira: ' + ', '.join(f'{j.ad} {j.sonuc["S"]:.1f}' for j in sira2))
    mevcut_hazirla(konf)
    t3 = []
    for j in sira2[:2]:
        t3.append(Is(3, j.ad, j.args, 0, j.out, degerlendir=('val_b32', 10), tam=True))   # seed 0: the Tur 2 run
        for t in (1, 2):
            t3.append(Is(3, j.ad, j.args, t, f'{K}/t3_{j.ad}_s{t}', degerlendir=('val_b32', 10), tam=True))
    tur_kos(t3)
    log('tur 3 bitti')
    print(sh(f'python3 {A}/kararla.py'), flush=True)
    log('arama bitti')


if __name__ == '__main__':
    sys.exit(main())
