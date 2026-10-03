#!/usr/bin/env bash
# Run several episode lists back to back, each with its own log.
#
#   tools/veri/zincir.sh [--bekle PID] LISTE1 GUNLUK1 [LISTE2 GUNLUK2 ...]
#
# Start it detached (setsid nohup ... &) so it does not depend on the shell
# that launched it. --bekle waits for a running batch to finish first.
WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ "${1:-}" = "--bekle" ]; then
	while kill -0 "$2" 2>/dev/null; do sleep 5; done
	shift 2
fi
while [ $# -ge 2 ]; do
	"$WS_DIR/tools/veri/toplu.sh" "$1" "$2"
	shift 2
done
