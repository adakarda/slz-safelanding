"""Duzeltme 29 tam karsilastirma, bir model icin: segmentasyon {gt, v3, v4} x kalkan {yok, eski, kilitli}, v4 dogrulama
(175 sahne) x 4 baslangic. Her deneme yeni ortam. Basari her zaman gercek etiketle olculur; politika, eski kalkan ve
kilitli kalkan segmentasyonun maskesini gorur.
  yok     : ortamin ic kalkani kapali (shield_m -1), kilitli kalkan yok
  eski    : ortamin ic kalkani (10 m; c13 tarifinin egitimdeki kalkani)
  kilitli : eski + kilitli kalkan (son sistem)

    PYTHONPATH=<donmus kod> $RL_PY faktor.py {flat|elev} MODEL.zip CIKTI.csv
"""
import csv
import os
import sys

from stable_baselines3 import PPO

from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.kilitli_kalkan import KilitliKalkan
from eland_rl.scenes import load_list

O = os.path.expanduser('~/eland_veri/rl/v4')
SEG = {'gt': (f'{O}/val.txt', 'gt'), 'v3': (f'{O}/val_v3.txt', 'pred'), 'v4': (f'{O}/val_v4.txt', 'pred')}
BASLANGIC = 4


def main():
    derinlik, model_yol, cikti = sys.argv[1:4]
    model = PPO.load(model_yol, device='cpu')
    rows = []
    for seg, (liste, kaynak) in SEG.items():
        scenes = load_list(liste, dist_cell_m=0.25)
        for kalkan in ('yok', 'eski', 'kilitli'):
            cfg = dict(max_t=30.0, randomise_dynamics=False, obs_mode='sem_depth_sora', diag_actions=True,
                       shield_m=-1.0 if kalkan == 'yok' else 10.0, gimbal=True, depth_mode=derinlik,
                       sem_source=kaynak, **REWARD_PRESETS['zemin_v3'])
            for i, sc in enumerate(scenes):
                for k in range(BASLANGIC):
                    env = LandingEnv(scenes, EnvConfig(**cfg))
                    obs, _ = env.reset(seed=k, options={'scene_index': i})
                    kk = KilitliKalkan(below_m=10.0)
                    kk.sifirla()
                    while True:
                        a = int(model.predict(obs, deterministic=True)[0])
                        if kalkan == 'kilitli':
                            pos, R = env.kamera_pozu()
                            a = kk(a, obs, pos[2], env.veh.t, pos, R, env.veh.pos[:2], env.veh.yaw, env.cam.rays)[0]
                        obs, r, done, trunc, info = env.step(int(a))
                        if done or trunc:
                            break
                    rows.append(dict(seg=seg, kalkan=kalkan, kaynak='floodnet' if 'floodnet' in sc.name else 'messi',
                                     scene=sc.name, start=k, outcome=info['outcome'], t=round(info['t'], 2),
                                     zemin_success=int(info['zemin_success']), landing_class=info['landing_class']))
    with open(cikti, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ozet = []
    for seg in SEG:
        r = [x for x in rows if x['seg'] == seg and x['kalkan'] == 'kilitli']
        ozet.append(f'{seg} %{100 * sum(x["zemin_success"] for x in r) / len(r):.1f}')
    print('kilitli kalkanla: ' + ', '.join(ozet))


if __name__ == '__main__':
    main()
