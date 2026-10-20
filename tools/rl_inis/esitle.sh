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
	--filter 'P /README.md' --filter 'P /esitle.sh' --filter 'P /requirements_*.txt' --filter 'P /arama/*/arama.log' \
	--exclude 'venv/' --exclude 'kos/' --exclude '__pycache__/' --exclude 'hiz/eski/' --exclude 'hiz/yeni/' \
	--exclude 'izle/' --exclude 'f4/kos/' --exclude 'eslesme/es1*/' \
	--exclude 'commit_*.sh' --exclude 'durum.json' --exclude 'denetim/*.json' --exclude 'anlat/veri.json' \
	--exclude '*.yedek' --exclude 'tanilama/messi_acilmis_crc.tsv' --exclude 'b2hiz/' --exclude 'gozlem/' --exclude 'birlesim/' \
	--include '*/' \
	--include '*.py' --include '*.sh' --include '*.md' --include '*.txt' --include '*.csv' --include '*.tsv' \
	--include '*.json' --include '*.js' --include 'arama/arama.log' \
	--exclude '*' \
	"$HOME/rl_inis/" "$HEDEF/"
# the search's round logs live in subfolders; keep them as text records
for t in b2hiz gozlem birlesim; do
	[ -f "$HOME/rl_inis/arama/$t/arama.log" ] && install -D -m 644 "$HOME/rl_inis/arama/$t/arama.log" "$HEDEF/arama/$t/arama.log"
done
find "$HEDEF" -type f -size +300k -print -delete | sed 's/^/buyuk, atlandi: /'
echo "tools/rl_inis: $(find "$HEDEF" -type f | wc -l) dosya, $(du -sh "$HEDEF" | cut -f1)"
