#!/bin/bash
# Bellek tasmasin diye PD egitimini durdur (3 egitim ayni anda, bos bellek < 1 GB). PD sonra yeniden kosulur.
P=$(pgrep -f '[-]-out /home/arda/rl_inis/kos/da_PD')
echo "PD PID: ${P:-yok}"; [ -n "$P" ] && kill $P
sleep 3; free -m | sed -n 2,3p
echo "[da] $(date +%H:%M) PD durduruldu: B1 ve B2 ile ayni anda 3 egitim bellegi tasiriyordu; PD sonra yeniden kosulacak (pd_tekrar.sh)" >> $HOME/rl_inis/kos/akis_b.out
