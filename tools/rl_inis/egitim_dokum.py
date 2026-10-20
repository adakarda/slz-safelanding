"""Butun egitim kosularinin ayarlari (args.json) ve degerlendirme dosyalari: farklarin tablosu icin."""
import glob
import json
import os

K = os.path.expanduser('~/rl_inis/kos')
alanlar = ['scenes', 'steps', 'seed', 'envs', 'reward', 'obs', 'sora_cell', 'sem_source', 'depth_mode',
           'sora_elev_tau', 'shield_train_m', 'mirror', 'encoder', 'ent_coef', 'land_hard', 'binary', 'lr', 'vec']
for d in sorted(glob.glob(os.path.join(K, '*'))):
    a = os.path.join(d, 'args.json')
    if not os.path.isdir(d) or not os.path.exists(a):
        continue
    j = json.load(open(a))
    j['scenes'] = os.path.basename(str(j.get('scenes', '')))
    ev = sorted(os.path.basename(x) for x in glob.glob(os.path.join(d, 'eval*')) + glob.glob(os.path.join(d, '*test*')))
    log = os.path.join(d, 'egitim.log')
    son = open(log).read().strip().splitlines()[-1][:90] if os.path.exists(log) else ''
    print(os.path.basename(d), {k: j.get(k) for k in alanlar if k in j}, ev, '|', son)
