#!/bin/bash
# M0 pilotu: bir AirSim dunyasini kamera kipinde ac, kareleri Windows'tan al (127.0.0.1; guvenlik duvari gerekmez),
# AirSim'i kapat, v3'u WSL'de olc. Bekci: Windows'ta bos bellek 30 s boyunca 500 MB altindaysa AirSim kapanir.
#
#   pilot_kos.sh [DUNYA_EXE (WSL yolu)] [OUT_ADI] [OLCUM betigi] [yakala.py ek secenekleri...]
#   varsayilan: AirSimNH, pilot_kareler, v3_olc.py
W=/mnt/c/Users/arda_/airsim
EXE=${1:-$W/AirSimNH/AirSimNH/WindowsNoEditor/AirSimNH.exe}
OUT_ADI=${2:-pilot_kareler}
OLCUM=${3:-v3_olc.py}
shift 3 2>/dev/null || shift $#
EXE_ADI=$(basename "$EXE")
PY=$W/venv/Scripts/python.exe
OUT=$W/$OUT_ADI; OUT_WIN="C:\\Users\\arda_\\airsim\\$OUT_ADI"
K=$HOME/rl_inis/kos
win_bos() { powershell.exe -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -dc 0-9; }
[ -f "$EXE" ] || { echo "[pilot] dunya yok: $EXE"; exit 1; }
touch $K/PILOT_CALISIYOR
kapat() { taskkill.exe /IM "$EXE_ADI" /F >/dev/null 2>&1; [ -n "${BEKCI:-}" ] && kill $BEKCI 2>/dev/null; rm -f $K/PILOT_CALISIYOR; }
trap kapat EXIT
tasklist.exe 2>/dev/null | grep -qi "$EXE_ADI" && { echo "[pilot] AirSim zaten acik, cikiyorum"; exit 1; }
while [ "$(win_bos)" -lt 2500 ]; do echo "[pilot] $(date +%H:%M) Windows bos bellek $(win_bos) MB, 2500 bekleniyor"; sleep 120; done
echo "[pilot] $(date +%H:%M) $EXE_ADI aciliyor (Windows bos $(win_bos) MB)"
"$EXE" -settings='C:\Users\arda_\airsim\pilot\settings_cv.json' -windowed -ResX=1280 -ResY=720 >/dev/null 2>&1 &
(
	dusuk=0
	while sleep 5; do
		b=$(win_bos); [ -z "$b" ] && continue
		if [ "$b" -lt 500 ]; then dusuk=$((dusuk + 5)); else dusuk=0; fi
		if [ $dusuk -ge 30 ]; then echo "[pilot] BEKCI: Windows bos bellek $b MB, AirSim kapatiliyor"; taskkill.exe /IM "$EXE_ADI" /F >/dev/null 2>&1; break; fi
	done
) &
BEKCI=$!
for _ in $(seq 1 240); do
	"$PY" -c "import socket; socket.create_connection(('127.0.0.1', 41451), 2)" 2>/dev/null && break
	sleep 1
done
"$PY" -c "import socket; socket.create_connection(('127.0.0.1', 41451), 2)" 2>/dev/null || { echo "[pilot] AirSim API acilmadi"; exit 1; }
echo "[pilot] $(date +%H:%M) API hazir, sahne yuklensin diye 15 s"
sleep 15
"$PY" 'C:\Users\arda_\airsim\pilot\yakala.py' --out "$OUT_WIN" --n 40 "$@" 2>&1 | tail -n 15
taskkill.exe /IM "$EXE_ADI" /F >/dev/null 2>&1
echo "[pilot] $(date +%H:%M) AirSim kapatildi; kare sayisi $(ls $OUT/*_rgb.png 2>/dev/null | wc -l)"
while [ "$(free -m | awk 'NR==2 {print $7}')" -lt 3500 ]; do sleep 60; done
echo "[pilot] $(date +%H:%M) v3 olcumu (WSL): $OLCUM"
cd /tmp && $HOME/v3_test/venv/bin/python $HOME/rl_inis/airsim_pilot/$OLCUM "$OUT" 2>&1 | grep -v -i warn | tail -n 90
