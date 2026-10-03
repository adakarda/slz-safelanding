#!/usr/bin/env bash
# Run a list of episodes one after another and log wall time per episode.
#
#   tools/veri/toplu.sh LISTE [GUNLUK]
#
# LISTE: one shell command per line, run from the workspace root, e.g.
#     POLITIKA="sabit --hiz 1.0" tools/veri/kosu.sh 1 k1_v1.0 veri_w3
# Empty lines and lines starting with # are skipped.
# GUNLUK gets one line per episode: start, end, seconds, exit code, command.
set -o pipefail
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LISTE="${1:?liste dosyasi gerekli}"
GUNLUK="${2:-/tmp/veri_toplu.log}"
: >"$GUNLUK"
: >"$GUNLUK.ayrinti"
while IFS= read -r line || [ -n "$line" ]; do
	case "$line" in '' | '#'*) continue ;; esac
	t0=$(date +%s)
	(cd "$WS_DIR" && bash -c "$line") </dev/null >>"$GUNLUK.ayrinti" 2>&1
	rc=$?
	t1=$(date +%s)
	echo "$(date -d @"$t0" +%H:%M:%S) $(date -d @"$t1" +%H:%M:%S) $((t1 - t0)) s rc=$rc | $line" >>"$GUNLUK"
	sleep 3
done <"$LISTE"
echo "bitti" >>"$GUNLUK"
