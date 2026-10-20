#!/bin/bash
# K74 varsayilani (2026-10-17): kosan kol (PA) bitsin, yeni Depth Anything kolu baslamasin.
# da_kollar.sh dongusu durduruldu; PA egitimi bitince burada degerlendirilir.
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4; O=$HOME/rl_inis/kos/da_PA
echo "[pa] bekliyor $(date +%H:%M)"
while pgrep -f '[-]-out /home/arda/rl_inis/kos/da_PA' >/dev/null; do sleep 60; done
[ -f $O/model.zip ] || { echo "[pa] model.zip yok"; tail -n 5 $O/egitim.log; exit 1; }
echo "[pa] egitim bitti $(date +%H:%M): $(tail -n 1 $O/egitim.log)"
cd $HOME/rl_inis
$RL_PY -u -m eland_rl.evaluate --scenes $D/test_foto.txt --sora-cell 0.25 --model $O/model.zip --starts 15 \
	--reward sora_v1 --obs sem_depth_sora --sem-source pred --oracle --out $O/eval_test_foto.csv >$O/eval_test_foto.txt 2>&1
grep -E '^(rl|rl_kalkan|duz_inis|kanal|gorus_kahini) ' $O/eval_test_foto.txt | cut -c1-200 | sed "s/^/[da] PA /"
echo "[da] PA bitti $(date +%H:%M); K74 varsayilani: PB/PC/PD baslatilmadi" | tee -a $HOME/rl_inis/kos/akis_b.out
