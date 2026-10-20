#!/bin/bash
# Duzeltme 4 kosularinin ozeti
for r in sora_v1_s0 paper_ent_s0; do
	echo "== $r"
	for odul in sora_v1 paper; do
		echo "-- degerlendirme odulu: $odul"
		grep -E '^(rl|duz_inis|rastgele) ' $HOME/rl_inis/kos/$r/eval_$odul.txt
	done
	echo "-- rl sahne bazinda (secili kural) ve eylemler:"
	awk '/^rl /{f=1; next} /^duz_inis /{f=0} f' $HOME/rl_inis/kos/$r/eval_sora_v1.txt
	python3 - "$r" <<'EOF'
import csv, sys
r = list(csv.DictReader(open(f'/home/arda/rl_inis/kos/{sys.argv[1]}/progress.csv')))
for x in r[::20] + [r[-1]]:
    print('  ', x['time/total_timesteps'], 'odul', round(float(x['rollout/ep_rew_mean']), 1),
          'uzunluk', round(float(x['rollout/ep_len_mean']), 1), 'entropi', x.get('train/entropy_loss', '')[:6])
EOF
done
