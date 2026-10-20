#!/bin/bash
# HEAD kodu (eski) ile yamali kopya (yeni) ayni izleri uretiyor mu?
source $HOME/rl_inis/ortam.sh
H=$HOME/rl_inis/hiz
AV=$(free -m | awk 'NR==2 {print $7}'); echo "mevcut bellek MB: $AV"
[ "$AV" -lt 1500 ] && { echo "bellek az, cikiyorum"; exit 1; }
rm -rf $H/eski $H/yeni; mkdir -p $H/eski $H/yeni
cd $HOME/ros2_ws && git archive HEAD src/eland_rl/eland_rl | tar -x -C $H/eski --strip-components=2
cp -r $HOME/ros2_ws/src/eland_rl/eland_rl $H/yeni/
diff -rq $H/eski/eland_rl $H/yeni/eland_rl --exclude=__pycache__ && echo "src = HEAD (temiz)"
$RL_PY $H/yama_hiz.py $H/yeni/eland_rl && $RL_PY $H/yama_hiz2.py $H/yeni/eland_rl
head -3 $HOME/eland_veri/rl/messi_ds4/train_foto.txt > $H/liste.txt
cd /tmp
for V in eski yeni; do
	echo "== $V"
	PYTHONPATH=$H/$V:$PYTHONPATH $RL_PY -c "import sys, eland_rl; print(eland_rl.__file__); sys.argv = ['iz', '$H/liste.txt', '$H/$V.npz']; exec(open('$H/iz_kaydi.py').read())"
done
$RL_PY -c "
import numpy as np
a, b = np.load('$H/eski.npz'), np.load('$H/yeni.npz')
for k in a.files:
    print(k, a[k].shape, 'AYNI' if np.array_equal(a[k], b[k]) else 'FARKLI')
print('SONUC:', 'birebir ayni' if all(np.array_equal(a[k], b[k]) for k in a.files) else 'FARK VAR')
"
