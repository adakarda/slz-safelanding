#!/bin/bash
# Sira (Duzeltme 16): gozlem turu bitince Faz 7'yi baslat. faz7_havada.sh kendi bekleme kurallarini da uygular
# (--havada ana dalda, egitim yok, AirSim kapali).
{
until grep -q 'birlesim bitti' $HOME/rl_inis/arama/birlesim/arama.log 2>/dev/null; do sleep 300; done
echo "[faz7_sonra] $(date '+%d.%m %H:%M') birlesim turu bitti; Faz 7 basliyor"
bash $HOME/rl_inis/airsim_pilot/faz7_havada.sh
echo "[faz7_sonra] $(date '+%d.%m %H:%M') zincir bitti"
exit
}
