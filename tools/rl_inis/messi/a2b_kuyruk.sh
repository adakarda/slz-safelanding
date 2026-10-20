#!/bin/bash
# Duzeltme 8: A1 (egitim + degerlendirme) bitince A2b'yi baslat.
while pgrep -f '[a]1_kos.sh' >/dev/null; do sleep 60; done
echo "[a2b] A1 bitti $(date +%H:%M); A2b basliyor"
AD=messi_a2b_s0 EK="--shield-train-m 10" EVAL_EK="--shield-train-m 10" bash $HOME/rl_inis/messi/a1_kos.sh
echo "[a2b] bitti $(date +%H:%M)"
