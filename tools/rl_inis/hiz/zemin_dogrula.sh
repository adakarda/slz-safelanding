#!/bin/bash
# Duzeltme 9 yamasini kopyada dene: eski ayarlar bit bit ayni mi, testler geciyor mu, yeni kural calisiyor mu
source $HOME/rl_inis/ortam.sh
H=$HOME/rl_inis/hiz
AV=$(free -m | awk 'NR==2 {print $7}'); echo "mevcut bellek MB: $AV"
[ "$AV" -lt 2000 ] && { echo "bellek az, cikiyorum"; exit 1; }
rm -rf $H/eski $H/yeni; mkdir -p $H/eski $H/yeni
cd $HOME/ros2_ws && git archive HEAD src/eland_rl/eland_rl | tar -x -C $H/eski --strip-components=2
git diff --quiet -- src/eland_rl || { echo "src HEAD'den farkli, cikiyorum"; exit 1; }
cp -r $HOME/ros2_ws/src/eland_rl/eland_rl $H/yeni/ && cp $HOME/ros2_ws/src/eland_rl/test/test_env.py $H/yeni/
$RL_PY $H/yama_zemin.py $H/yeni/eland_rl $H/yeni/test_env.py || exit 1
head -3 $HOME/eland_veri/rl/messi_ds4/train_foto.txt > $H/liste.txt
cd /tmp
for V in eski yeni; do
	echo "== iz $V"
	PYTHONPATH=$H/$V:$PYTHONPATH $RL_PY -c "import sys; sys.argv = ['iz', '$H/liste.txt', '$H/$V.npz']; exec(open('$H/iz_kaydi.py').read())" 2>&1 | tail -6
done
$RL_PY -c "
import numpy as np
a, b = np.load('$H/eski.npz'), np.load('$H/yeni.npz')
print('ESKI AYARLAR:', 'birebir ayni' if all(np.array_equal(a[k], b[k]) for k in a.files) else 'FARK VAR ' + str([k for k in a.files if not np.array_equal(a[k], b[k])]))
"
echo "== testler (yeni)"; cd $H/yeni && $RL_PY -m pytest -q -p no:cacheprovider test_env.py 2>&1 | tail -3
echo "== zemin_v1 + ayna, gercek sahneler, rastgele eylem"
cd /tmp && PYTHONPATH=$H/yeni:$PYTHONPATH $RL_PY -c "
import collections, numpy as np
from eland_rl.env import REWARD_PRESETS, EnvConfig, LandingEnv
from eland_rl.scenes import load_list
sc = load_list('$H/liste.txt', dist_cell_m=0.25)
env = LandingEnv(sc, EnvConfig(obs_mode='sem_depth_sora', mirror=True, sora_metric=False, **REWARD_PRESETS['zemin_v1']))
rng = np.random.default_rng(0); c = collections.Counter(); r_end = collections.Counter(); ayna = 0
for ep in range(60):
    o, info = env.reset(seed=ep); ayna += info['scene'].endswith('|ayna'); d = False
    while not d:
        o, r, d, _, info = env.step(9 if rng.random() < 0.6 else int(rng.integers(0, 9)))
    c[info['outcome']] += 1
    if info['landing_class'] >= 0: r_end[(info['landing_class'], info['r_end'])] += 1
print('aynali bolum', ayna, '/ 60 | sonuclar', dict(c)); print('inis sinifi -> odul', dict(sorted(r_end.items())))
"
