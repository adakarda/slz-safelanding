"""Faz 7 (21.10) fixes, both found in the broken batch's logs:

1. run_airsim.sh, --havada: the reposition command is a single best-effort message; when it is lost the vehicle stays
   at the takeoff height and the start fails ("havada hedefe varilamadi", konum z -28.7 for a 26.2 m target).
   It is now sent again every 5 s until the vehicle is there.
2. run_airsim.sh, temizle: inis_sina.sh sends TERM right after it sees the HATA line, while the EXIT trap is already
   cleaning up; the TERM trap ('exit 130') cut the cleanup short before PX4 was killed, and that PX4 made every later
   start fail ("calisan bir sim var", 119 of 120 Faz 7 starts). The cleanup now ignores INT and TERM.
3. inis_sina.sh: before each attempt, a PX4 left in AirSim's own rootfs (rootfs_airsim) is closed. A Gazebo PX4
   (other working directory) is never touched.

    python3 yama_faz7.py
"""
import os

S = os.path.expanduser('~/ros2_ws/src/eland_airsim/scripts')


def yama(yol, eski, yeni):
    s = open(yol, encoding='utf-8').read()
    if yeni in s:
        print('zaten var:', os.path.basename(yol)); return
    assert s.count(eski) == 1, (yol, eski)
    open(yol, 'w', encoding='utf-8').write(s.replace(eski, yeni))
    print('yamandi:', os.path.basename(yol))


r = f'{S}/run_airsim.sh'
yama(r, 'temizle() {\n\techo "[run_airsim] kapatiliyor..."\n',
     'temizle() {\n'
     '\ttrap \'\' INT TERM     # a TERM during cleanup cut it short and left PX4 running (Faz 7, 2026-10-21)\n'
     '\techo "[run_airsim] kapatiliyor..."\n')
yama(r, '\thedefe_uc "$H_N" "$H_E" "$TAKEOFF_ALT"\n'
        '\tfor _ in $(seq 1 90); do vardi "$H_N" "$H_E" "$TAKEOFF_ALT" && break; sleep 1; done\n'
        '\thedefe_uc "$H_N" "$H_E" "$H_ALT"\n'
        '\tfor _ in $(seq 1 60); do vardi "$H_N" "$H_E" "$H_ALT" && break; sleep 1; done\n',
     '\t# the command is one best-effort message and can be lost (Faz 7, 2026-10-21): sent again every 5 s until there\n'
     '\thedefe_uc "$H_N" "$H_E" "$TAKEOFF_ALT"\n'
     '\tfor s in $(seq 1 90); do\n'
     '\t\tvardi "$H_N" "$H_E" "$TAKEOFF_ALT" && break\n'
     '\t\t[ $((s % 5)) = 0 ] && hedefe_uc "$H_N" "$H_E" "$TAKEOFF_ALT"\n'
     '\t\tsleep 1\n'
     '\tdone\n'
     '\thedefe_uc "$H_N" "$H_E" "$H_ALT"\n'
     '\tfor s in $(seq 1 60); do\n'
     '\t\tvardi "$H_N" "$H_E" "$H_ALT" && break\n'
     '\t\t[ $((s % 5)) = 0 ] && hedefe_uc "$H_N" "$H_E" "$H_ALT"\n'
     '\t\tsleep 1\n'
     '\tdone\n')
i = f'{S}/inis_sina.sh'
yama(i, '\t\tD=$KOK/k$(printf %02d $i)$([ "$deneme" -gt 1 ] && echo "_$deneme")\n',
     '\t\t# a PX4 left by an earlier attempt blocks every later start (Faz 7, 2026-10-21). Only AirSim\'s own PX4\n'
     '\t\t# (working directory rootfs_airsim) is closed; a Gazebo session is never touched.\n'
     '\t\tfor p in $(pgrep -x px4); do\n'
     '\t\t\tcase "$(readlink /proc/$p/cwd 2>/dev/null)" in\n'
     '\t\t\t*rootfs_airsim*) echo "[inis] UYARI: onceki denemeden kalan AirSim PX4\'u ($p) kapatiliyor"\n'
     '\t\t\t\tkill $p 2>/dev/null; sleep 3; kill -9 $p 2>/dev/null; sleep 5 ;;\n'
     '\t\t\tesac\n'
     '\t\tdone\n'
     '\t\tD=$KOK/k$(printf %02d $i)$([ "$deneme" -gt 1 ] && echo "_$deneme")\n')
