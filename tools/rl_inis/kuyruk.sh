#!/bin/bash
# Butun kuyruk on planda calisir; wsl.exe istemcisi bagli kalir, WSL bosta kapanmaz.
# Akis A: A1 (surdur) -> A2b. Akis B: Depth Anything kollari. Bellek: ayni anda en fazla 2 egitim.
K=$HOME/rl_inis/kos
if pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null; then echo "zaten kosan egitim var"; exit 1; fi
touch $K/KUYRUK_CALISIYOR; trap 'rm -f $K/KUYRUK_CALISIYOR' EXIT
echo "kuyruk basladi $(date +%H:%M)"
( bash $HOME/rl_inis/messi/a1_kos.sh
  AD=messi_a2b_s0 EK="--shield-train-m 10" EVAL_EK="--shield-train-m 10" bash $HOME/rl_inis/messi/a1_kos.sh ) > $K/akis_a.out 2>&1 &
bash $HOME/rl_inis/derinlik/da_kollar.sh > $K/akis_b.out 2>&1 &
wait
echo "kuyruk bitti $(date +%H:%M)"; echo "--- akis A"; tail -n 30 $K/akis_a.out; echo "--- akis B"; tail -n 30 $K/akis_b.out
