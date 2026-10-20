#!/bin/bash
# Zincir surerken tez ciktilarini saatte bir yenile; tarama ve gozlem turu bitince en iyi kosunun egitim izlerini uret.
# Hafif is (tek cekirdek, birkac dakika); egitimlerin yaninda calisabilir. En cok 60 saat.
{
cd $HOME/rl_inis
L=$HOME/rl_inis/arama/arama.log
GL=$HOME/rl_inis/arama/gozlem/arama.log
arama_izi=0; gozlem_izi=0
for _ in $(seq 1 60); do
	nice -n 15 bash py.sh gorsel/tez_ciktilari.py > /tmp/tez_ciktilari.log 2>&1 && echo "[son_islem] $(date '+%d.%m %H:%M') tez ciktilari yenilendi"
	if [ $arama_izi = 0 ] && grep -q 'arama bitti' $L 2>/dev/null; then
		D=$(python3 gorsel/en_iyi.py arama)
		[ -n "$D" ] && nice -n 15 bash py.sh gorsel/egitim_izleri.py --kosu $D --cikti /mnt/c/Users/arda_/rl_gorsel/tez > /tmp/izler_arama.log 2>&1 \
			&& echo "[son_islem] $(date '+%d.%m %H:%M') tarama en iyisinin izleri: $D"
		arama_izi=1
	fi
	if [ $gozlem_izi = 0 ] && grep -q 'gozlem bitti' $GL 2>/dev/null; then
		D=$(python3 gorsel/en_iyi.py gozlem)
		[ -n "$D" ] && nice -n 15 bash py.sh gorsel/egitim_izleri.py --kosu $D --cikti /mnt/c/Users/arda_/rl_gorsel/tez > /tmp/izler_gozlem.log 2>&1 \
			&& echo "[son_islem] $(date '+%d.%m %H:%M') gozlem cesidinin izleri: $D"
		gozlem_izi=1
	fi
	grep -q 'zincir bitti' /mnt/c/Users/arda_/AppData/Local/Temp/claude/C--Users-arda-/d850e9d6-317d-406c-ad99-74e2041430be/tasks/bq4i1fznt.output 2>/dev/null && break
	sleep 3600
done
echo "[son_islem] bitti"
exit
}
