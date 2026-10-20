#!/bin/bash
cd $HOME/ros2_ws
echo "== dallar"; git branch -a --sort=-committerdate | head -12
for f in tools/veri/sim_panel.py tools/veri/bozucu_canli.py tools/veri/ruzgar_canli.py tools/veri/sim_olay.py src/eland_mapping/eland_mapping/yukseklik_gozlemci.py; do
	printf "%-55s " $f; for b in main inis-yasasi bozucu-canli rl-inis; do git cat-file -e $b:$f 2>/dev/null && printf "%s " $b; done; echo
done
echo "== eland_mode parametreleri (yasa/secim)"; grep -n "declare_parameter" src/eland_mode/include/emergency_landing_mode.hpp | head -30
echo "== obstacle_driver parametreleri"; grep -n "declare_parameter\|def _from_parameters" src/eland_sim/eland_sim/obstacle_driver.py | head -20
echo "== run_sim secenekleri"; grep -oE "\-\-[a-z-]+\)" src/eland_sim/scripts/run_sim.sh | sort -u | tr '\n' ' '; echo
grep -oE "RUN_SIM_[A-Z_]+" src/eland_sim/scripts/run_sim.sh | sort -u | tr '\n' ' '; echo
