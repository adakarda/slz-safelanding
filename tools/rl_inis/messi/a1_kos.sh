#!/bin/bash
# Duzeltme 6, A1: MESSI egitimi (sora_v1 + SORA kanali + entropi), 2M adim, tohum 0; sonra degerlendirme.
# Yarim kalan kosu (ckpt var, model.zip yok) son checkpoint'ten surer (yurutme notu 2026-10-17).
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4
O=$HOME/rl_inis/kos/${AD:-messi_a1_s0}; mkdir -p $O
cd $HOME/rl_inis
if [ ! -f $O/model.zip ]; then
	C=$(ls -v $O/ckpt/model_*_steps.zip 2>/dev/null | tail -n 1)
	LOG=$O/egitim.log; DEVAM=
	if [ -n "$C" ]; then DEVAM="--resume $C"; LOG=$O/egitim_devam$(basename $C .zip | tr -dc 0-9).log; fi
	echo "[a1] $(basename $O) basladi $(date +%H:%M) ${DEVAM:-sifirdan}"
	$RL_PY -u -m eland_rl.train --scenes $D/train.txt --shard --sora-cell 0.25 --steps ${ADIM:-2000000} --seed ${TOHUM:-0} \
		--reward sora_v1 --ent-coef 0.01 --obs sem_depth_sora --out $O ${EK:-} $DEVAM >$LOG 2>&1
	echo "[a1] $(basename $O) egitim cikis $? $(date +%H:%M): $(tail -n 1 $LOG)"
fi
bash $HOME/rl_inis/messi/degerlendir.sh $O
