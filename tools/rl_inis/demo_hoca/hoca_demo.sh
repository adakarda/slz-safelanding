#!/bin/bash
# Hoca gosterimi (Arda, 28.10): AirSim + PX4 + segmentasyon + RL politikasi (c13 s0, gimbal, eski kalkan 10 m) +
# kontrol istasyonu. Acilan pencereler:
#   - AirSim (asagi kamera ve AirSim segmentasyonu alt pencereleri, --alt-pencere)
#   - v4 paneli: kamera | v4 maskesi | AirSim etiketi, canli dogruluk (/eland/v3/panel; gosterim_izle.py; yalniz v4)
#   - RL komut ekrani: politikanin gordugu ve komutu (/eland/rl/gorus; gosterim_izle.py)
#   - kontrol istasyonu (HUD + klavye): pencereye tikla; 1 arm, 2 kalkis, 3 manuel, W/A/S/D Q/E R/F, 0 = RL ile acil inis
# Calistirma: masaustundeki AirSim_Gosterim_v4.bat / AirSim_Gosterim_GT.bat ya da
#   bash ~/rl_inis/demo/hoca/hoca_demo.sh [v4|gt]     (gt: AirSim'in gercek segmentasyonu; Faz 7: 24/30 guvenli)
{
M=$HOME/rl_inis/kos/arama/t2_c13_f_kayarak_kalkan/model.zip
S=$HOME/ros2_ws/src/eland_airsim/scripts
echo "== Hoca gosterimi =="
if pgrep -f '[e]land_rl\.train|[e]land_rl\.evaluate|[f]aktor\.py' >/dev/null; then
	echo "Bir RL egitimi ya da degerlendirmesi calisiyor; AirSim'e bellek yetmez. Once onu bitir/durdur."
	read -r -p "Enter ile kapat" _; exit 1
fi
if pgrep -x px4 >/dev/null || pgrep -f '[r]un_airsim\.sh' >/dev/null; then
	echo "Calisan bir benzetim var (px4/run_airsim). Once onu kapat."
	read -r -p "Enter ile kapat" _; exit 1
fi
if [ "${1:-v4}" = gt ]; then
	SEG=()
	echo "Segmentasyon: AirSim'in gercek etiketi"
else
	SEG=(--v3 --seg-model "$HOME/v4_seg/best_v4.pth" --seg-adi v4)
	echo "Segmentasyon: bizim v4 modelimiz"
fi
echo "Pencereler ~1-2 dk icinde acilir. Kontrol istasyonu penceresine tikla, sonra:"
echo "  1 = arm, 2 = kalkis, W/A/S/D/Q/E/R/F ile ucur, 0 = RL ile acil inis. Kapatmak icin bu pencerede Ctrl+C."
(
	source /opt/ros/jazzy/setup.bash
	exec python3 /home/arda/rl_inis/demo/hoca/gosterim_izle.py
) > /tmp/gosterim_izle.log 2>&1 &
IZ=$!
bash "$S/run_airsim.sh" --baslangic 29.5,123.1 --rl "$M" --kalkan 10 --gimbal "${SEG[@]}" --alt-pencere --station
kill $IZ 2>/dev/null
}
