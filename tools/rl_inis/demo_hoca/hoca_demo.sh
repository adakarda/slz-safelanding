#!/bin/bash
# Hoca gosterimi (Arda, 28.10): AirSim + PX4 + bizim segmentasyon modeli (v4) + RL politikasi (c13 s0, gimbal,
# eski kalkan 10 m) + kontrol istasyonu. Acilan pencereler:
#   - AirSim (asagi kamera ve AirSim segmentasyonu alt pencereleri, --izle)
#   - v4 paneli: kamera | v4 maskesi | AirSim etiketi, canli dogruluk (/eland/v3/panel)
#   - RL komut ekrani: politikanin gordugu ve komutu (/eland/rl/gorus)
#   - kontrol istasyonu (HUD + klavye): pencereye tikla; 1 arm, 2 kalkis, 3 manuel, W/A/S/D Q/E R/F, 0 = RL ile acil inis
# Calistirma: masaustundeki AirSim_Gosterim.bat ya da
#   bash ~/rl_inis/demo/hoca/hoca_demo.sh
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
echo "Pencereler ~1-2 dk icinde acilir. Kontrol istasyonu penceresine tikla, sonra:"
echo "  1 = arm, 2 = kalkis, W/A/S/D/Q/E/R/F ile ucur, 0 = RL ile acil inis. Kapatmak icin bu pencerede Ctrl+C."
exec bash "$S/run_airsim.sh" --baslangic 29.5,123.1 --rl "$M" --kalkan 10 --gimbal \
	--v3 --seg-model "$HOME/v4_seg/best_v4.pth" --seg-adi v4 --izle --station
}
