#!/bin/bash
# F4 pilot: 15 baslangic (baslangiclar.txt), her biri ayri sim; sonuc satirlari ozet.txt'ye.
#   bash kos_hepsi.sh [gt|topic]
SRC=${1:-gt}
D=$HOME/rl_inis/f4
: >$D/ozet_$SRC.txt
while read -r K X Y H YAWD || [ -n "$K" ]; do
	[ -z "$K" ] && continue
	echo "[f4] baslangic $K: $X $Y $H m, yaw $YAWD"
	bash $D/kos_tek.sh ${SRC}_b$K $X $Y $H $YAWD $SRC 2>&1 | grep -E '^SONUC|\[f4\]' | tee -a $D/ozet_$SRC.txt
	sleep 5
done <$D/baslangiclar.txt
echo "[f4] bitti"
