#!/bin/bash
# bir sonraki sonuca kadar bekle: bir degerlendirme biter ya da butun kuyruklar biter
K=$HOME/rl_inis/kos
say() { ls $K/da_*/eval_test_foto.csv $K/messi_a*_s0/eval_train_ornek20.csv $K/b_*/eval_val.csv 2>/dev/null | wc -l; }
isaret() { ls $K/*_CALISIYOR 2>/dev/null | wc -l; }
N=$(say); i=0
echo "bekleme basladi $(date +%H:%M): biten sonuc sayisi $N, acik kuyruk $(isaret)"
while true; do
	sleep 60; i=$((i + 1))
	if [ $((i % 30)) -eq 0 ]; then
		for P in $K/da_P?/progress.csv $K/b_*/progress.csv; do
			[ -f $P ] && echo "$(date +%H:%M) ${P#$K/} adim=$(tail -n 1 $P | cut -d, -f1)"
		done 2>/dev/null | tail -4
		free -m | awk 'NR==2 {print "  bellek MB:", $3} NR==3 {print "  swap MB:", $3}'
	fi
	[ "$(isaret)" = 0 ] && { echo "OLAY: butun kuyruklar bitti $(date +%H:%M)"; break; }
	[ "$(say)" != "$N" ] && { echo "OLAY: yeni sonuc $(date +%H:%M)"; break; }
done
echo "--- akis B (DA)"; tail -n 8 $K/akis_b.out 2>/dev/null | cut -c1-160
echo "--- B deneyi"; tail -n 12 $K/kuyruk_b.out 2>/dev/null
