#!/bin/bash
# anlik durum: surecler, bellek, A1 ve da_P0 ilerlemesi
echo "== uptime: $(uptime)"
free -h | head -3
nproc
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null
echo "== egitim surecleri"; pgrep -af 'eland_rl\.(train|evaluate)|_kos.sh|da_kollar|kuyruk' || echo yok
echo "== sim surecleri"; pgrep -af 'px4|gz sim|ros2 launch' | head -5 || true
for K in messi_a1_s0 da_P0; do
  P=$HOME/rl_inis/kos/$K/progress.csv
  [ -f $P ] || continue
  echo "== $K"
  python3 - "$P" <<'PY'
import csv, sys
r = list(csv.DictReader(open(sys.argv[1])))
h = r[0].keys()
last = r[-1]
for k in ('time/total_timesteps', 'time/time_elapsed', 'time/fps', 'rollout/ep_rew_mean', 'rollout/ep_len_mean',
          'train/approx_kl', 'train/clip_fraction', 'train/entropy_loss', 'train/explained_variance'):
    print(f'  {k}: {last.get(k)}')
PY
done
