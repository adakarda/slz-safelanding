#!/bin/bash
# A1 politikasini (MESSI, sora_v1) Gazebo'da izle.
#   bash ~/rl_inis/rl_izle_a1.sh [baslangic_no 0-14] [model.zip]
# Butun egitim, degerlendirme ve vekil surecleri bu surede duraklatilir (bellegi bosaltmaz, CPU'yu birakir);
# cikista devam ederler. Bellek bekcisi: bos bellek 700 MB'in altina inerse sim kapatilir.
K=${1:-0}
M=${2:-$HOME/rl_inis/kos/messi_a1_s0/model.zip}
alt() { for c in $(pgrep -P "$1"); do echo "$c"; alt "$c"; done; }
# sim icin yer: en az 4.5 GB bos bellek (bir egitim bitince olur)
while [ "$(free -m | awk 'NR==2 {print $7}')" -lt 4500 ]; do
	echo "[izle] $(date +%H:%M) bos bellek $(free -m | awk 'NR==2 {print $7}') MB; 4500 MB bekleniyor (bir egitim bitince)..."
	sleep 30
done
PIDS=""
for p in $(pgrep -f '[e]land_rl\.(train|evaluate|vekil)'); do PIDS="$PIDS $p $(alt $p)"; done
if [ -n "$PIDS" ]; then kill -STOP $PIDS; echo "[izle] egitimler duraklatildi"; fi
BEKCI=""
devam() {
	[ -n "$BEKCI" ] && kill $BEKCI 2>/dev/null
	if [ -n "$PIDS" ]; then kill -CONT $PIDS 2>/dev/null; echo "[izle] egitimler devam ediyor"; fi
}
trap devam EXIT
(
	while sleep 5; do
		a=$(free -m | awk 'NR==2 {print $7}')
		if [ "$a" -lt 700 ]; then
			echo "[izle] bos bellek $a MB: sim kapatiliyor (egitimleri korumak icin)"
			pkill -INT -f '[r]un_sim.sh'; sleep 5; pkill -x px4; break
		fi
	done
) &
BEKCI=$!
echo "[izle] bos bellek: $(free -m | awk 'NR==2 {print $7}') MB"
bash $HOME/rl_inis/rl_izle.sh "$K" "$M"
