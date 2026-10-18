#!/bin/bash
# Ortografik harita cekimi: AirSimNH'yi settings_orto.json ile ac, orto.py'yi Windows'ta kos, kapat.
W=/mnt/c/Users/arda_/airsim
EXE=${1:-$W/AirSimNH/AirSimNH/WindowsNoEditor/AirSimNH.exe}
OUT_ADI=${2:-orto_nh}
EXE_ADI=$(basename "$EXE")
PY=$W/venv/Scripts/python.exe
K=$HOME/rl_inis/kos
win_bos() { powershell.exe -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -dc 0-9; }
tasklist.exe 2>/dev/null | grep -qi "$EXE_ADI" && { echo "[orto] AirSim zaten acik"; exit 1; }
touch $K/PILOT_CALISIYOR
trap 'taskkill.exe /IM "$EXE_ADI" /F >/dev/null 2>&1; rm -f $K/PILOT_CALISIYOR' EXIT
while [ "$(win_bos)" -lt 2500 ]; do echo "[orto] $(date +%H:%M) Windows bos $(win_bos) MB, bekleniyor"; sleep 60; done
"$EXE" -settings='C:\Users\arda_\airsim\pilot\settings_orto.json' -windowed -ResX=1280 -ResY=720 >/dev/null 2>&1 &
for _ in $(seq 1 240); do
	"$PY" -c "import socket; socket.create_connection(('127.0.0.1', 41451), 2)" 2>/dev/null && break
	sleep 1
done
sleep 15
"$PY" 'C:\Users\arda_\airsim\pilot\orto.py' --out 'C:\Users\arda_\airsim\'"$OUT_ADI" 2>&1 | tail -n 25
echo "[orto] $(date +%H:%M) bitti: $(ls $W/$OUT_ADI/*_gt8.png 2>/dev/null | wc -l) karo"
