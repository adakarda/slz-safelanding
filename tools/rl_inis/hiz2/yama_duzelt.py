"""Fixes after the 21.10 evening (both found in the logs):
  run_airsim.sh: --hizli-son 2 reached the mode as an integer ROS parameter; rl_landing_mode declares a double and
    aborted at start (InvalidParameterTypeException), so all 30 starts of the amendment 23 batch failed. Now %.2f.
  h23_karar.py: no landings in an arm crashed it (median of nothing); it now reports and stops.

    python3 yama_duzelt.py
"""
import os

H = os.path.expanduser('~')


def yama(p, pairs, atomik=False):
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        if new in s:
            continue
        assert s.count(old) == 1, (p, old)
        s = s.replace(old, new)
    if atomik:
        tmp = p + '.yeni'
        open(tmp, 'w', encoding='utf-8').write(s)
        os.chmod(tmp, os.stat(p).st_mode)
        os.replace(tmp, p)
    else:
        open(p, 'w', encoding='utf-8').write(s)
    print('yamandi:', p)


yama(f'{H}/ros2_ws/src/eland_airsim/scripts/run_airsim.sh', [
    ('\t\t\t${HIZLI_SON:+--ros-args -p hizli_son_irtifa_m:=$HIZLI_SON} >"$LOG_DIR/rl_mod.log" 2>&1 &\n',
     '\t\t\t${HIZLI_SON:+--ros-args -p hizli_son_irtifa_m:=$(awk -v k="$HIZLI_SON" \'BEGIN{printf "%.2f", k}\')} \\\n'
     '\t\t\t>"$LOG_DIR/rl_mod.log" 2>&1 &      # a ROS double: "2" would arrive as an integer and abort the mode\n'),
], atomik=True)
yama(f'{H}/rl_inis/hiz2/h23_karar.py', [
    ("def ozet(d, ad):\n    indi = [r for r in d.values() if r.get('sonuc') == 'indi']\n",
     "def ozet(d, ad):\n    indi = [r for r in d.values() if r.get('sonuc') == 'indi']\n"
     "    if not indi:\n"
     "        print(f'{ad}: hic inis yok ({sorted(set(r.get(\"sonuc\") for r in d.values()))})')\n"
     "        print('KARAR: olcum gecersiz')\n"
     "        raise SystemExit(1)\n"),
])
