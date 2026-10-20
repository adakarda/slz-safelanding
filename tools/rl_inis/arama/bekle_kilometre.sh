#!/bin/bash
# Taramanin bir kilometre tasina kadar bekle (arama.log'da ifade gorulunce ya da arama sureci olunce cik).
#   bash bekle_kilometre.sh "tur 1 bitti"
{
L=$HOME/rl_inis/arama/arama.log
until grep -q "$1" "$L" 2>/dev/null; do
	pgrep -f '[a]rama/arama\.py' >/dev/null || { echo "arama sureci yok"; tail -5 "$L"; exit 1; }
	sleep 120
done
grep "$1" "$L" | tail -1
exit
}
