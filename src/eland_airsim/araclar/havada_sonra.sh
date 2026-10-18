#!/bin/bash
# Havada baslangic denemesi, ikinci kez: D ve E egitimleri bitince (bellek ve CPU bosken) 2 kosu, dal havada
# (~/ros2_ws_h). Ikisi de inerse havada dali airsim'e birlestirilir.
{
K=$HOME/rl_inis/kos
H=$HOME/ros2_ws_h/src/eland_airsim/scripts
sleep 120
while [ -f $K/D_CALISIYOR ] || [ -f $K/E_CALISIYOR ] || pgrep -f '[e]land_rl\.(train|evaluate)' >/dev/null \
	|| pgrep -f '[r]un_airsim\.sh|[i]nis_sina\.sh' >/dev/null; do
	sleep 60
done
echo "[havada] $(date +%H:%M) egitimler bitti; havada baslangic denemesi (B2-s0, GT, kalkan 10)"
python3 $H/havada_sec.py --tohum 11 --n 2 --cikti $HOME/eland_veri/havada_dene.csv
bash $H/inis_sina.sh $HOME/eland_veri/havada_dene.csv --rl $K/b_B2_s0/model.zip --kalkan 10 --etiket havada_dene2 \
	| grep -E "kosu [0-9]+ \(|^   |bitti|guvenli sinifa|UYARI|baslamadi|HATA"
S=$(ls -td $HOME/eland_veri/_gunlukler/airsim_inis_havada_dene2_*/ | head -1)
(cd /tmp && ~/v3_test/venv/bin/python $HOME/rl_inis/airsim_pilot/inis_harita.py /mnt/c/Users/arda_/airsim/orto_nh/harita.npz ${S}sonuc.jsonl) | tail -1
INDI=$(grep -c '"sonuc": "indi"' ${S}sonuc.jsonl)
UCTU=$(grep -h "havada:" ${S}k*.out 2>/dev/null | wc -l)
echo "[havada] $(date +%H:%M) $INDI/2 indi; hedefe varan deneme $UCTU"
if [ "$INDI" = 2 ]; then
	cd $HOME/ros2_ws && git merge -q --no-ff -m "$(printf 'Birlestir: havada dali (run_airsim.sh --havada); AirSim denemesi 2/2 indi\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>')" havada \
		&& echo "[havada] havada dali airsim'e birlestirildi: $(git log --oneline -1)"
fi
exit
}
