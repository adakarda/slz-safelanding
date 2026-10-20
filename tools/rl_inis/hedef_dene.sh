#!/bin/bash
# run_airsim.sh'teki hedefe_uc'un urettigi komutu PX4'suz yazdir
LAT0=47.6402939; LON0=-122.139617; ALT0=122.146
ll=$(python3 -c "import math, sys; la, lo, n, e = map(float, sys.argv[1:]); r = 6378137.0
print(f'{la + math.degrees(n / r):.8f} {lo + math.degrees(e / (r * math.cos(math.radians(la)))):.8f}')" "$LAT0" "$LON0" 30.9 -34.7)
amsl=$(awk -v a="$ALT0" -v h=27.8 'BEGIN {printf "%.2f", a + h}')
echo "ll=[$ll] amsl=[$amsl]"
echo "{command: 192, param1: -1.0, param2: 1.0, param4: .nan, param5: ${ll% *}, param6: ${ll#* }, param7: $amsl, target_system: 1}"
