#!/bin/bash
# One command to see the current state of the system, in the scenario every
# measurement in docs/DURUM.md 19-20 was taken on: fixed spawn, fixed mob
# layout, three people and two vehicles moving on drawn routes.
#
# Not a replacement for run_sim.sh -- it is run_sim.sh with the arguments that
# make two runs comparable, plus the leftover-process cleanup that has ruined
# more measurements here than any bug (two obstacle_drivers publishing
# conflicting truth on the same topic look exactly like a tracking failure).
# No `set -u`: ROS's own setup.bash reads unset variables (AMENT_TRACE_SETUP_
# FILES) and dies under it.
set -o pipefail

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MODE="${1:-hud}"

usage() {
	cat <<'EOF'
dene.sh [mod]

  hud       (varsayilan) Gazebo penceresi + HUD + kontrol istasyonu.
            Kendin ucur, kendin tetikle. Tuslar HUD penceresinde:
              t  kalkis      m  Emergency Landing modunu sec
              9  modu kayittan dusur (PX4 kendi Return'une doner)
  otomatik  pencere yok; kalkis + mod secimi otomatik, karar dongusunun
            sayilari sona yazilir (aday hizi, durum gecisi, aday kaybi).
  olcum     pencere yok; 90 s izleme skoru (gercek vs kestirilen hiz,
            izlenmeyen karelerin sebebi).

Ortam degiskeni: KISI (varsayilan 3), ARAC (varsayilan 2).
EOF
}

case "$MODE" in
-h | --help | help) usage; exit 0 ;;
hud | otomatik | olcum) ;;
*) echo "bilinmeyen mod '$MODE'"; usage; exit 1 ;;
esac

cd "$WS_DIR" || exit 1
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash

echo "[dene] derleniyor..."
colcon build --packages-select eland_msgs eland_common eland_sim eland_mapping \
	eland_perception eland_viz eland_mode 2>&1 | tail -2 || exit 1
# shellcheck disable=SC1091
source install/setup.bash

echo "[dene] onceki kosudan kalanlar temizleniyor..."
pkill -f "gz sim" 2>/dev/null
pkill -x px4 2>/dev/null
pkill -f MicroXRCEAgent 2>/dev/null
pkill -f "ros2 launch" 2>/dev/null
for n in obstacle_driv tracker_no detector_no mapping_no perception_no \
	emergency_landing hud_no control_stat image_bridg; do
	pkill -f "$n" 2>/dev/null
done
# PX4 does not release its ports the instant it dies; starting the next run
# too early gives "PX4 topic'leri gorunmedi" and no simulation at all.
sleep 10

PARAMS="/tmp/eland_dene_params.yaml"
# A pinned scenario: a randomly drawn mob layout is not comparable with the
# numbers already recorded. The variant is built from the installed defaults
# because the world generator reads this same file and needs every key in it.
python3 "$WS_DIR/tools/make_params.py" "$PARAMS" 	obstacle_driver.randomize_mobs=false 	"obstacle_driver.person_count=${KISI:-3}" 	"obstacle_driver.vehicle_count=${ARAC:-2}" >/dev/null || exit 1

echo "[dene] senaryo: sabit spawn, sabit mob duzeni, ${KISI:-3} kisi + ${ARAC:-2} arac"

case "$MODE" in
hud)
	echo "[dene] pencere aciliyor. Cikmak icin Ctrl+C."
	exec "$WS_DIR/src/eland_sim/scripts/run_sim.sh" --fixed --params "$PARAMS"
	;;
otomatik)
	"$WS_DIR/src/eland_sim/scripts/run_sim.sh" --fixed --headless --no-hud \
		--auto --params "$PARAMS" >/tmp/eland_dene.log 2>&1 &
	RUN=$!
	echo "[dene] kalkis ve mod secimi bekleniyor (~40 s)..."
	sleep 40
	echo "[dene] iniş izleniyor (105 s)..."
	export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH:-}"
	timeout 150 python3 - <<'PY'
import time

import rclpy
from eland_msgs.msg import LandingCandidate
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)

DECISION_QOS = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                          durability=DurabilityPolicy.VOLATILE,
                          history=HistoryPolicy.KEEP_LAST, depth=1)


class Watch(Node):
    """The three numbers that describe the decision loop.

    Rate says whether a decision is published at all, the invalid count says
    how often the detector had nowhere to offer, and the gaps say whether any
    of those stretches crossed the 3 s after which the mode abandons a
    descent. Before the fix in docs/DURUM.md 20 this run showed 79 of 152
    frames with no candidate and three abandoned descents.
    """

    def __init__(self):
        super().__init__('dene_watch')
        self.t = []
        self.invalid = 0
        self.streaks = []
        self.t_bad = None
        self.t0 = time.time()
        self.create_subscription(LandingCandidate, '/eland/candidate',
                                 self.on_cand, DECISION_QOS)
        self.create_timer(1.0, self.tick)

    def on_cand(self, msg):
        now = time.time()
        self.t.append(now)
        if not msg.valid:
            self.invalid += 1
            if self.t_bad is None:
                self.t_bad = now
        elif self.t_bad is not None:
            self.streaks.append(now - self.t_bad)
            self.t_bad = None

    def tick(self):
        if time.time() - self.t0 < 105.0:
            return
        n = len(self.t)
        span = self.t[-1] - self.t[0] if n > 1 else 0.0
        hz = (n - 1) / span if span > 0 else 0.0
        print(f'aday yayini      : {n} mesaj, {hz:.2f} Hz')
        print(f'aday uretilmeyen : {self.invalid}/{n} kare')
        over = sum(1 for d in self.streaks if d >= 3.0)
        longest = max(self.streaks) if self.streaks else 0.0
        print(f'aday bosluklari  : {len(self.streaks)} seri, en uzunu '
              f'{longest:.1f} s, 3 s esigini asan {over}')
        raise SystemExit(0)


rclpy.init()
node = Watch()
try:
    rclpy.spin(node)
except SystemExit:
    pass
finally:
    node.destroy_node()
    rclpy.try_shutdown()
PY
	echo "--- mod durum gecisleri ---"
	grep -oE "(SEARCH|APPROACH|VALIDATE|HOLD|ABORT|COMMIT) -> .*" \
		/tmp/eland_logs/pipeline.log || echo "(gecis yok)"
	echo -n "aday kaybi: "
	grep -c "candidate lost" /tmp/eland_logs/pipeline.log
	echo "--- karar karesi (ms, p50/p95) ---"
	grep -o "decision ms (p50/p95):.*" /tmp/eland_logs/pipeline.log | tail -1
	kill -INT "$RUN" 2>/dev/null
	sleep 5
	pkill -f "gz sim" 2>/dev/null
	pkill -x px4 2>/dev/null
	pkill -f MicroXRCEAgent 2>/dev/null
	echo "[dene] bitti. Tam gunluk: /tmp/eland_logs/pipeline.log"
	;;
olcum)
	SCORER="$WS_DIR/tools/measure_tracking.py"
	"$WS_DIR/src/eland_sim/scripts/run_sim.sh" --fixed --headless --no-hud \
		--takeoff 20 --params "$PARAMS" >/tmp/eland_dene.log 2>&1 &
	RUN=$!
	echo "[dene] kalkis bekleniyor (~105 s)..."
	sleep 105
	export PYTHONPATH="/usr/lib/python3/dist-packages:${PYTHONPATH:-}"
	VEHICLES="${ARAC:-2}" timeout 130 python3 "$SCORER" 90
	kill -INT "$RUN" 2>/dev/null
	sleep 5
	pkill -f "gz sim" 2>/dev/null
	pkill -x px4 2>/dev/null
	pkill -f MicroXRCEAgent 2>/dev/null
	echo "[dene] bitti."
	;;
esac
