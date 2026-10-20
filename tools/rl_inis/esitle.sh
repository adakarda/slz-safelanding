#!/bin/bash
# Mirror ~/rl_inis (scripts and small text results only) into the repo: tools/rl_inis/.
# Not copied: venv/, kos/ (models and run outputs), data, images, arrays, run logs, one-off commit helpers,
# and the MESSI file list (the dataset is private). Files written only in the repo (README.md, this script,
# requirements_*.txt) are protected from --delete.
#
#   bash tools/rl_inis/esitle.sh        (on the machine that has ~/rl_inis)
set -e
HEDEF=$HOME/ros2_ws/tools/rl_inis
mkdir -p "$HEDEF"
rsync -a --delete --delete-excluded --prune-empty-dirs \
	--filter 'P /README.md' --filter 'P /esitle.sh' --filter 'P /requirements_*.txt' \
	--exclude 'venv/' --exclude 'kos/' --exclude '__pycache__/' --exclude 'hiz/eski/' --exclude 'hiz/yeni/' \
	--exclude 'izle/' --exclude 'f4/kos/' --exclude 'eslesme/es1*/' \
	--exclude 'commit_*.sh' --exclude 'durum.json' --exclude 'denetim/*.json' --exclude 'anlat/veri.json' \
	--exclude '*.yedek' --exclude 'yedek_gel/' --exclude 'tanilama/messi_acilmis_crc.tsv' \
	--include '*/' \
	--include '*.py' --include '*.sh' --include '*.md' --include '*.txt' --include '*.csv' --include '*.tsv' \
	--include '*.json' --include '*.js' --include 'arama/arama.log' --include 'arama/*/arama.log' \
	--exclude '*' \
	"$HOME/rl_inis/" "$HEDEF/"
find "$HEDEF" -type f -size +300k -print -delete | sed 's/^/buyuk, atlandi: /'
echo "tools/rl_inis: $(find "$HEDEF" -type f | wc -l) dosya, $(du -sh "$HEDEF" | cut -f1)"
