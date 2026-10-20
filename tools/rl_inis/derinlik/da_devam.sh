#!/bin/bash
# K74 cevabi (Arda, 2026-10-17): Depth Anything devam. PA'nin degerlendirmesi bitince PB, PC, PD sirayla.
# da_kollar.sh biten kollari (P0, PA) atlar. DA_CALISIYOR isareti uyanik tutmayi besler.
K=$HOME/rl_inis/kos
touch $K/DA_CALISIYOR; trap 'rm -f $K/DA_CALISIYOR' EXIT
echo "[da-devam] PA bekleniyor $(date +%H:%M)"
while [ ! -f $K/da_PA/eval_test_foto.csv ] || pgrep -f '[p]a_bitir.sh' >/dev/null; do sleep 60; done
echo "[da-devam] PA bitti, PB/PC/PD basliyor $(date +%H:%M)" | tee -a $K/akis_b.out
bash $HOME/rl_inis/derinlik/da_kollar.sh >> $K/akis_b.out 2>&1
echo "[da-devam] bitti $(date +%H:%M)"; tail -n 20 $K/akis_b.out
