#!/bin/bash
# --resume duman testi: 2 ortam, 4096 adim egit, 2048 adim checkpointinden 8192'ye devam et
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4
O=/tmp/devam_duman; rm -rf $O
cd $HOME/rl_inis
head -4 $D/train_foto.txt > /tmp/devam_liste.txt
$RL_PY -u -m eland_rl.train --scenes /tmp/devam_liste.txt --shard --sora-cell 0.25 --steps 4096 --envs 2 --vec dummy \
	--reward sora_v1 --ent-coef 0.01 --obs sem_depth_sora --out $O >$O.log1 2>&1 || { tail -20 $O.log1; exit 1; }
ls $O/ckpt
C=$(ls $O/ckpt | head -1)
$RL_PY -u -m eland_rl.train --scenes /tmp/devam_liste.txt --shard --sora-cell 0.25 --steps 8192 --envs 2 --vec dummy \
	--reward sora_v1 --ent-coef 0.01 --obs sem_depth_sora --out $O --resume $O/ckpt/$C >$O.log2 2>&1 || { tail -20 $O.log2; exit 1; }
tail -1 $O.log2
ls $O $O/ckpt
python3 - $O <<'PY'
import csv, sys, os
for f in ('progress.csv', [d for d in os.listdir(sys.argv[1]) if d.startswith('devam')][0] + '/progress.csv'):
    r = list(csv.DictReader(open(os.path.join(sys.argv[1], f))))
    print(f, [(x['time/total_timesteps'], x.get('train/learning_rate')) for x in r])
PY
