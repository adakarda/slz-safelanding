#!/bin/bash
# Faz 3 duman testi: calisan run_airsim kosusunun durumu (gunluk klasoru arguman).
D=${1:-$(ls -td ~/eland_veri/_gunlukler/airsim_* | head -1)}
echo "== $D"
echo "-- kopru"; tail -3 "$D/kopru.log"
echo "-- algi/mod (son olaylar)"
grep -v "^\s*$" "$D/pipeline.log" | grep -iE "emergency|landing|site|mode|detector|error|warn|state|phase|asama|inis" | tail -15
echo "-- AirSim gercek durum"
~/airsim-venv/bin/python - <<'PY'
from eland_airsim import istemci
c = istemci.connect(timeout_s=5)
k = c.simGetGroundTruthKinematics()
p, v = k.position, k.linear_velocity
print(f'NED x {p.x_val:.2f} y {p.y_val:.2f} z {p.z_val:.2f}  hiz {v.x_val:.2f} {v.y_val:.2f} {v.z_val:.2f}')
PY
