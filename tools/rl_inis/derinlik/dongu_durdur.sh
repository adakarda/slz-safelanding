#!/bin/bash
# da_kollar.sh dongusunu durdur; kosan PA egitimine dokunma
P=$(pgrep -f '[b]ash /home/arda/rl_inis/derinlik/da_kollar.sh')
echo "dongu PID: ${P:-yok}"
[ -n "$P" ] && kill $P
sleep 2
echo "dongu kaldi mi: $(pgrep -f '[d]a_kollar.sh' || echo hayir)"
echo "PA egitimi: $(pgrep -f '[-]-out /home/arda/rl_inis/kos/da_PA' || echo YOK)"
echo "A1: $(pgrep -f '[-]-out /home/arda/rl_inis/kos/messi_a1_s0' | head -1 || echo YOK)"
echo "kuyruk: $(pgrep -f '[k]uyruk.sh' || echo YOK)"
echo "[da] $(date +%H:%M) K74 varsayilani: dongu durduruldu, PA bitince PB/PC/PD baslamayacak" >> $HOME/rl_inis/kos/akis_b.out
