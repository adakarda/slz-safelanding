"""Paper videosundaki "Policy Training at N steps" gibi: bir kosunun kayit noktalari ayni sahnede, ayni 4 baslangictan
ucar; izler gercek MESSI fotografinin ustune cizilir. Cikti: PNG izgara + WebM video (+ ogrenme egrisi PNG).

    bash ~/rl_inis/py.sh gorsel/egitim_izleri.py --kosu kos/b_B2_s0 --cikti /mnt/c/Users/arda_/rl_gorsel

Sahne secimi: val_b32'de fotografi olan kareler icinde, kosunun eval_val.csv'sine gore son modelin basardigi ama
duz alcalmanin basaramadigi baslangic sayisi en cok olan kare (politikanin bir sey ogrendigi yer). Ortam
degerlendirmeyle ayni (30 s, nominal dinamik, argmax, reset(seed=k)), yani son modelin izi eval_val.csv'deki
sonucun aynisidir.
"""
import argparse
import collections
import csv
import glob
import json
import os

import cv2
import numpy as np
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.policy import POLICY_KWARGS, policy_kwargs
from eland_rl.scenes import load_list

MESSI = '/home/arda/eland_veri/rl/messi_rl'
VAL = '/home/arda/eland_veri/rl/messi_ds4/val_b32.txt'
RENK = [(80, 230, 60), (240, 220, 40), (40, 140, 255), (40, 220, 255)]   # BGR: green, cyan, orange, yellow
ADIMLAR = [0, 100_000, 200_000, 300_000, 500_000, 1_000_000]


def foto_yolu():
    yol = {}
    for m in csv.DictReader(open(f'{MESSI}/manifest.csv')):
        p = f"{MESSI}/{m['img']}"
        if os.path.exists(p):
            yol[m['id'].replace('/', '__')] = p
    return yol


def degerlendirme(kosu):
    """val_b32 evaluation of the run: eval_val.csv (pre-registered arms) or eval_val_b32_10.csv (screening)."""
    for ad in ('eval_val.csv', 'eval_val_b32_10.csv'):
        if os.path.exists(os.path.join(kosu, ad)):
            return os.path.join(kosu, ad)
    raise SystemExit(f'{kosu}: val_b32 degerlendirmesi yok')


def sahne_sec(kosu, scenes, fotolar, n):
    rs = list(csv.DictReader(open(degerlendirme(kosu))))
    if not any(r['method'] == 'duz_inis' for r in rs):      # screening evaluations hold RL only
        rs += [r for r in csv.DictReader(open(os.path.expanduser('~/rl_inis/kos/b_B1_s0/eval_val.csv')))
               if r['method'] == 'duz_inis']
    ok = {(r['scene'], int(r['start'])): r['zemin_success'] == '1' for r in rs if r['method'] == 'rl'}
    duz = {(r['scene'], int(r['start'])): r['zemin_success'] == '1' for r in rs if r['method'] == 'duz_inis'}
    best = None
    for i, sc in enumerate(scenes):
        if sc.name not in fotolar:
            continue
        ogrendi = [k for k in range(10) if ok.get((sc.name, k)) and not duz.get((sc.name, k))]
        diger = [k for k in range(10) if k not in ogrendi]
        puan = (len(ogrendi), sum(ok.get((sc.name, k), False) for k in range(10)))
        if best is None or puan > best[0]:
            best = (puan, i, (ogrendi + diger)[:n])
    if best is None:
        raise SystemExit('val_b32 icinde fotografi olan kare yok')
    return best[1], best[2]


def kayit_dizinleri(kosu):
    """The run's own directory and, for a screening run resumed from round 1 or copied from an earlier arm,
    the directories its checkpoints live in."""
    ds = [kosu]
    if os.path.exists(os.path.join(kosu, 'MEVCUT')):                 # amendment 15c: copied from an earlier arm
        kaynak = open(os.path.join(kosu, 'MEVCUT')).read().strip()
        ds.append(kaynak.split('/ckpt/')[0] if '/ckpt/' in kaynak else os.path.dirname(kaynak))
    t1 = os.path.join(os.path.dirname(kosu), 't1_' + os.path.basename(kosu)[3:])
    if os.path.basename(kosu).startswith('t2_') and os.path.isdir(t1):
        ds.append(t1)
    ga = os.path.join(os.path.dirname(kosu), 'a_' + os.path.basename(kosu)[2:])     # observation round G-B <- G-A
    if os.path.basename(kosu).startswith('b_') and os.path.isdir(ga):
        ds.append(ga)
    return ds


def model_yukle(kosu, adim, env):
    if adim == 0:       # the untrained policy: same network, random weights, the run's seed
        a = json.load(open(os.path.join(kosu, 'args.json')))
        kw = POLICY_KWARGS if a.get('encoder', 'paper') == 'paper' else policy_kwargs(a['encoder'])
        return PPO('MlpPolicy', env, policy_kwargs=kw, seed=a.get('seed', 0), device='cpu')
    for d in kayit_dizinleri(kosu):
        p = os.path.join(d, 'ckpt', f'model_{adim}_steps.zip')
        if os.path.exists(p):
            return PPO.load(p, device='cpu')
    if adim == 1_000_000:
        return PPO.load(os.path.join(kosu, 'model.zip'), device='cpu')
    raise FileNotFoundError(f'{kosu}: {adim} adim kaydi yok')


def ucur(env, model, i, k):
    obs, _ = env.reset(seed=k, options={'scene_index': i})
    iz = [env.veh.pos.copy()]
    while True:
        a = int(model.predict(obs, deterministic=True)[0])
        obs, r, done, trunc, info = env.step(a)
        iz.append(env.veh.pos.copy())
        if done or trunc:
            return np.array(iz), info


def piksel(sc, xy, W, H):
    u = (xy[:, 0] / sc.size[0] + 0.5) * W
    v = (0.5 - xy[:, 1] / sc.size[1]) * H
    return np.stack([u, v], 1)


def zemin(sc, foto, W, H):
    img = cv2.resize(foto, (W, H), interpolation=cv2.INTER_AREA)
    img = (img * 0.82).astype(np.uint8)
    hedef, _, _ = sc._target_grid((6, 5), 2.0)          # landable and clear of people/vehicles: faint green
    m = cv2.resize(hedef.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST).astype(bool)
    img[m] = (img[m] * 0.75 + np.array([40, 200, 40]) * 0.25).astype(np.uint8)
    return img


def ciz(img, sc, izler, adim, kac=None):
    H, W = img.shape[:2]
    out = img.copy()
    for j, (iz, info) in enumerate(izler):
        p = piksel(sc, iz[:kac] if kac else iz, W, H).astype(np.int32)
        cv2.polylines(out, [p], False, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.polylines(out, [p], False, RENK[j], 3, cv2.LINE_AA)
        cv2.circle(out, tuple(p[0]), 7, (255, 255, 255), 2, cv2.LINE_AA)
        if kac is None or kac >= len(iz):
            q = tuple(p[-1])
            if info['zemin_success']:
                cv2.circle(out, q, 10, (60, 200, 60), -1, cv2.LINE_AA)
                cv2.circle(out, q, 10, (0, 0, 0), 2, cv2.LINE_AA)
            elif info['outcome'] == 'timeout':
                cv2.rectangle(out, (q[0] - 8, q[1] - 8), (q[0] + 8, q[1] + 8), (160, 160, 160), -1)
                cv2.rectangle(out, (q[0] - 8, q[1] - 8), (q[0] + 8, q[1] + 8), (0, 0, 0), 2)
            else:
                for d in ((-9, -9, 9, 9), (-9, 9, 9, -9)):
                    cv2.line(out, (q[0] + d[0], q[1] + d[1]), (q[0] + d[2], q[1] + d[3]), (0, 0, 0), 6, cv2.LINE_AA)
                    cv2.line(out, (q[0] + d[0], q[1] + d[1]), (q[0] + d[2], q[1] + d[3]), (60, 60, 230), 3, cv2.LINE_AA)
    bar = np.full((54, W, 3), 22, np.uint8)
    basari = sum(bool(info['zemin_success']) for _, info in izler)
    cv2.putText(bar, f'Politika: {adim:,} adim'.replace(',', ' '), (14, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.95,
                (255, 255, 255), 2, cv2.LINE_AA)
    if kac is None or kac >= max(len(iz) for iz, _ in izler):
        cv2.putText(bar, f'{basari}/{len(izler)} guvenli', (W - 190, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.85,
                    (120, 230, 120) if basari else (200, 200, 200), 2, cv2.LINE_AA)
    return np.concatenate([bar, out], 0)


def egri(kosu, cikti):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows = []
    for f in sorted(glob.glob(os.path.join(kosu, 'monitor_[0-9]*.monitor.csv'))):
        rows += [r for r in csv.DictReader(l for l in open(f) if not l.startswith('#'))]
    rows.sort(key=lambda r: float(r['t']))
    adim = np.cumsum([int(r['l']) for r in rows])
    rew = np.array([float(r['r']) for r in rows])
    ok = np.array([r['zemin_success'] == 'True' for r in rows], float)
    k = 300
    kayan = lambda x: np.convolve(x, np.ones(k) / k, mode='valid')  # noqa: E731
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].plot(adim[k - 1:], kayan(rew), color='#1d5f8a')
    ax[0].set(xlabel='adim', ylabel='bolum odulu (300 bolum ortalamasi)', title='Egitim odulu')
    ax[1].plot(adim[k - 1:], 100 * kayan(ok), color='#2c7a4b')
    ax[1].set(xlabel='adim', ylabel='zemin basarisi % (egitimde, 90 s)', title='Egitimde basari')
    for a in ax:
        a.grid(alpha=0.3)
        a.set_xlim(0, 1_000_000)
    fig.suptitle(os.path.basename(kosu))
    fig.tight_layout()
    fig.savefig(cikti, dpi=130)
    print('egri', cikti, f'bolum {len(rows)}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kosu', default='kos/b_B2_s0')
    ap.add_argument('--n', type=int, default=4)
    ap.add_argument('--cikti', default='/mnt/c/Users/arda_/rl_gorsel')
    ap.add_argument('--genislik', type=int, default=960)
    a = ap.parse_args()
    kosu = os.path.abspath(a.kosu)
    ad = os.path.basename(kosu)
    os.makedirs(a.cikti, exist_ok=True)
    fotolar = foto_yolu()
    scenes = load_list(VAL, dist_cell_m=0.25)
    i, baslar = sahne_sec(kosu, scenes, fotolar, a.n)
    sc = scenes[i]
    print('sahne', sc.name, 'baslangiclar', baslar)
    a_ = json.load(open(os.path.join(kosu, 'args.json')))
    env = LandingEnv(scenes, EnvConfig(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora',
                                       diag_actions=bool(a_.get('diag')),
                                       kanallar=tuple(k for k in (a_.get('kanallar') or '').split(',') if k),
                                       shield_m=float(a_.get('shield_train_m', -1.0)),
                                       **REWARD_PRESETS[a_['reward']]))
    foto = cv2.imread(fotolar[sc.name])
    W = a.genislik
    H = int(round(W * sc.size[1] / sc.size[0]))
    taban = zemin(sc, foto, W, H)
    paneller, video = [], None
    vpath = os.path.join(a.cikti, f'{ad}_egitim_izleri.webm')
    for adim in ADIMLAR:
        model = model_yukle(kosu, adim, env)
        izler = [ucur(env, model, i, k) for k in baslar]
        sonuc = collections.Counter('basari' if inf['zemin_success'] else inf['outcome'] for _, inf in izler)
        print(f'{adim:>8d} adim: {dict(sonuc)}; sure {[round(inf["t"], 1) for _, inf in izler]}')
        paneller.append(ciz(taban, sc, izler, adim))
        uz = max(len(iz) for iz, _ in izler)
        for kac in list(range(2, uz, 2)) + [uz] * 25:          # paths grow, then hold for ~2.5 s
            kare = ciz(taban, sc, izler, adim, kac)
            if video is None:
                video = cv2.VideoWriter(vpath, cv2.VideoWriter_fourcc(*'VP80'), 10, (kare.shape[1], kare.shape[0]))
            video.write(kare)
    video.release()
    k2 = [cv2.resize(p, (p.shape[1] // 2, p.shape[0] // 2), interpolation=cv2.INTER_AREA) for p in paneller]
    izgara = np.concatenate([np.concatenate(k2[:3], 1), np.concatenate(k2[3:], 1)], 0)
    ppath = os.path.join(a.cikti, f'{ad}_egitim_izleri.png')
    cv2.imwrite(ppath, izgara)
    print('png', ppath, 'video', vpath)
    egri(kosu, os.path.join(a.cikti, f'{ad}_egitim_egrisi.png'))


if __name__ == '__main__':
    main()
