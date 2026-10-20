"""Kosularin anlik durumu -> JSON (salt okuma): ilerleme, hiz, egriler, degerlendirme sonuclari."""
import ast
import csv
import glob
import json
import os
import re
import subprocess
import sys
import time

K = os.path.expanduser('~/rl_inis/kos')
RUNS = [('messi_a1_s0', 'A1', 'MESSI ana egitim: sora_v1 + SORA kanali, butun Agamim (696 kare)'),
        ('messi_a2b_s0', 'A2b', 'A1 + kalkan egitimin icinde (shield_m 10)'),
        ('da_P0', 'P0', 'DA deneyi referans: GT maske, duz derinlik'),
        ('da_PA', 'PA', 'DA deneyi: v3 tahmin maskesi, duz derinlik'),
        ('da_PB', 'PB', 'DA deneyi: v3 + Depth Anything goreli yukseklik kanali'),
        ('da_PC', 'PC', 'DA deneyi: v3 + SORA kanalinda yukseklik esigi 0.12'),
        ('da_PD', 'PD', 'DA deneyi: v3 + yukseklik kanali + esik 0.12')]
RUNS += [(f'b_{k}_s{t}', f'{k}-s{t}', a) for t in (0, 1, 2) for k, a in
         (('B0', 'B deneyi: bugunku odul'), ('B1', 'B deneyi: zemin_v1'), ('B2', 'B deneyi: zemin_v1 + aynalama'))]
TARGET = {'A1': 2_000_000, 'A2b': 2_000_000}
BIN = 50_000


def rows(p):
    with open(p) as f:
        return list(csv.DictReader(f))


def monitor(path_glob, start, stop, n_env=4):
    eps = []
    for p in sorted(glob.glob(path_glob)):
        with open(p) as f:
            f.readline()
            cum = 0
            for r in csv.DictReader(f):
                cum += int(r['l'])
                s = start + n_env * cum
                if s < stop:
                    eps.append((s, r['sora_success'] == 'True', r['outcome'], float(r['r'])))
    return eps


def evals(d):
    out = {}
    for p in glob.glob(os.path.join(d, 'eval_*.txt')):
        name = os.path.basename(p)[5:-4]
        res = {}
        for ln in open(p, errors='replace'):
            m = re.match(r'^(\w+)\s+SORA basari\s+([\d.]+) %.*?odul\s+(-?[\d.]+).*?(\{.*\})', ln)
            if m:
                res[m.group(1)] = {'sora': float(m.group(2)), 'odul': float(m.group(3)),
                                   'sonuc': ast.literal_eval(m.group(4))}
        if res:
            out[name] = res
    return out


now = time.time()
procs = subprocess.run(['pgrep', '-af', 'eland_rl'], capture_output=True, text=True).stdout
data = {'zaman': time.strftime('%Y-%m-%d %H:%M'), 'kosular': []}
for d, ad, aciklama in RUNS:
    D = os.path.join(K, d)
    run = {'ad': ad, 'klasor': d, 'aciklama': aciklama, 'hedef': TARGET.get(ad, 1_000_000)}
    if not os.path.isdir(D):
        run['durum'] = 'sirada'
        data['kosular'].append(run)
        continue
    parts = sorted(glob.glob(os.path.join(D, 'devam*')), key=lambda p: int(re.sub(r'\D', '', os.path.basename(p))))
    starts = [0] + [int(re.sub(r'\D', '', os.path.basename(p))) for p in parts]
    prog_files = [os.path.join(D, 'progress.csv')] + [os.path.join(p, 'progress.csv') for p in parts]
    last = None
    for p in prog_files[::-1]:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            r = rows(p)
            if r:
                last, last_mtime = r[-1], os.path.getmtime(p)
                break
    eps = []
    globs = [os.path.join(D, 'monitor_[0-9].monitor.csv')] + [os.path.join(D, f'monitor_devam{s}_[0-9].monitor.csv') for s in starts[1:]]
    for i, g in enumerate(globs):
        eps += monitor(g, starts[i], starts[i + 1] if i + 1 < len(starts) else 10 ** 12)
    eps.sort()
    curve = []
    for b in range(0, (eps[-1][0] // BIN + 1) * BIN if eps else 0, BIN):
        e = [x for x in eps if b <= x[0] < b + BIN]
        if len(e) >= 20:
            curve.append({'adim': b + BIN // 2, 'sora': round(100 * sum(x[1] for x in e) / len(e), 1),
                          'timeout': round(100 * sum(x[2] == 'timeout' for x in e) / len(e), 1),
                          'guvensiz': round(100 * sum(x[2] == 'unsafe_landing' for x in e) / len(e), 1), 'n': len(e)})
    run['egri'] = curve
    run['kesintiler'] = starts[1:]
    run['bolum'] = len(eps)
    if last:
        g = lambda k: float(last[k]) if last.get(k) not in (None, '') else None  # noqa: E731
        run.update(adim=int(g('time/total_timesteps')), fps=g('time/fps'), ep_odul=g('rollout/ep_rew_mean'),
                   ep_uzunluk=g('rollout/ep_len_mean'), kl=g('train/approx_kl'), clip=g('train/clip_fraction'),
                   entropi=g('train/entropy_loss'), acik_varyans=g('train/explained_variance'),
                   son_guncelleme_dk=round((now - last_mtime) / 60, 1))
    run['degerlendirme'] = evals(D)
    egitimde = f'--out {D}' in procs and 'eland_rl.train' in procs.split(f'--out {D}')[0].rsplit('\n', 1)[-1]
    deger = any(f'--model {D}/' in ln and 'evaluate' in ln for ln in procs.splitlines())
    if os.path.exists(os.path.join(D, 'model.zip')):
        run['durum'] = 'degerlendiriliyor' if deger else ('bitti' if run['degerlendirme'] else 'egitim bitti')
    else:
        run['durum'] = 'egitimde' if egitimde else 'durdu'
    data['kosular'].append(run)
m = subprocess.run(['free', '-m'], capture_output=True, text=True).stdout.split('\n')
data['bellek_mb'] = {'kullanilan': int(m[1].split()[2]), 'toplam': int(m[1].split()[1]), 'swap': int(m[2].split()[2])}
json.dump(data, sys.stdout, ensure_ascii=False)
