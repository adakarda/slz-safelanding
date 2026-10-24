"""Duzeltme 27 degerlendirmesi: 0004 ucusunun 40 karesi (egitimde yok) x 10 baslangic, 30 s, nominal dinamik, argmax,
gimbal, yontemler rl ve rl_kalkan2. HER DENEME YENI BIR ORTAMLA (bir onceki denemenin durumu tasinmasin; 25.10'da
paylasilan ortamda ayni baslangicin farkli sure verdigi goruldu).

    PYTHONPATH=<donmus kod> $RL_PY degerlendir.py KOL MODEL.zip CIKTI.csv
"""
import csv
import os
import sys

import numpy as np
from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.kilitli_kalkan import KilitliKalkan
from eland_rl.scenes import load_list

LISTE = os.path.expanduser('~/eland_veri/rl/messi_ds4/test_foto.txt')
KOL_AYAR = {'A_irtifa': {}, 'B_yok': {'depth_norm_m': 1e9}, 'C_da': {'depth_mode': 'elev'}}


def main():
    kol, model_yol, cikti = sys.argv[1:4]
    scenes = load_list(LISTE, dist_cell_m=0.25)
    cfg = dict(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', diag_actions=True, shield_m=10.0,
               gimbal=True, **REWARD_PRESETS['zemin_v3'], **KOL_AYAR[kol])
    model = PPO.load(model_yol, device='cpu')
    rows = []
    for yontem in ('rl', 'rl_kalkan2'):
        for i, sc in enumerate(scenes):
            for k in range(10):
                env = LandingEnv(scenes, EnvConfig(**cfg))
                obs, _ = env.reset(seed=k, options={'scene_index': i})
                kk = KilitliKalkan(below_m=10.0)
                kk.sifirla()
                while True:
                    a = int(model.predict(obs, deterministic=True)[0])
                    if yontem == 'rl_kalkan2':
                        pos, R = env.kamera_pozu()
                        a = kk(a, obs, pos[2], env.veh.t, pos, R, env.veh.pos[:2], env.veh.yaw, env.cam.rays)[0]
                    obs, r, done, trunc, info = env.step(int(a))
                    if done or trunc:
                        break
                rows.append(dict(method=yontem, scene=sc.name, start=k, outcome=info['outcome'], t=round(info['t'], 2),
                                 zemin_success=int(info['zemin_success']), landing_class=info['landing_class']))
    with open(cikti, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ozet = []
    for y in ('rl', 'rl_kalkan2'):
        r = [x for x in rows if x['method'] == y]
        ok = [x['t'] for x in r if x['zemin_success']]
        u = sum(x['outcome'] != 'timeout' and not x['zemin_success'] for x in r)
        ozet.append(f'{y} B {100 * len(ok) / len(r):.1f} T {np.mean(ok) if ok else 30:.1f} s U {100 * u / len(r):.1f}')
    print(' | '.join(ozet))


if __name__ == '__main__':
    main()
