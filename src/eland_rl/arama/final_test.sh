#!/bin/bash
# Duzeltme 17: final test (IrYamim, test.txt, 20 kare x 15 baslangic). BIR KEZ ve yalniz Arda "kos" deyince calistir.
#   bash ~/rl_inis/final_test.sh MODEL_DIZINI [MODEL_DIZINI ...]     (final modelin tohumlari)
# B1'in uc tohumu kiyas olarak her zaman eklenir. Sonuclar <dizin>/eval_final_test.csv
{
source $HOME/rl_inis/ortam.sh
D=$HOME/eland_veri/rl/messi_ds4
[ -f $HOME/rl_inis/kos/FINAL_TEST_YAPILDI ] && { echo "final test zaten yapildi: $(cat $HOME/rl_inis/kos/FINAL_TEST_YAPILDI)"; exit 1; }
for d in "$@" $HOME/rl_inis/kos/b_B1_s0 $HOME/rl_inis/kos/b_B1_s1 $HOME/rl_inis/kos/b_B1_s2; do
	A=$(python3 -c "import json,sys; a=json.load(open(sys.argv[1])); print('--reward', a['reward'], '--diag' if a.get('diag') else '', '--kanallar ' + a['kanallar'] if a.get('kanallar') else '', '--shield-train-m ' + str(a['shield_train_m']) if a.get('shield_train_m', -1) >= 0 else '')" $d/args.json)
	echo "[final] $(date +%H:%M) $d $A"
	$RL_PY -u -m eland_rl.evaluate --scenes $D/test.txt --sora-cell 0.25 --model $d/model.zip --starts 15 --obs sem_depth_sora \
		$A --oracle --out $d/eval_final_test.csv > $d/eval_final_test.txt 2>&1
done
date '+%d.%m.%Y %H:%M' > $HOME/rl_inis/kos/FINAL_TEST_YAPILDI
echo "[final] bitti"
exit
}
