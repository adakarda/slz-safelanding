"""A ULog's parameters that differ from the vehicle's defaults (what parameters.bson held at that flight).

    python3 ulg_param.py LOG.ulg
"""
import sys

from pyulog import ULog

u = ULog(sys.argv[1], message_name_filter_list=[], parse_header_only=True)
cur = u.initial_parameters
dflt = {}
try:
    # ULog default-parameter messages: bit 0 system defaults, bit 1 current setup (airframe) defaults
    d = u.get_default_parameters(1) or u.get_default_parameters(0)
    dflt = d or {}
except Exception as e:  # noqa: BLE001
    print('varsayilan parametre yok:', e)
print(f'{len(cur)} parametre, {len(dflt)} varsayilan')
fark = {k: v for k, v in cur.items() if k in dflt and dflt[k] != v}
for k in sorted(fark):
    print(f'{k:22s} {fark[k]!r:>14}  (varsayilan {dflt[k]!r})')
print('SYS_AUTOSTART', cur.get('SYS_AUTOSTART'), 'MPC_Z_VEL_MAX_DN', cur.get('MPC_Z_VEL_MAX_DN'),
      'MPC_THR_HOVER', cur.get('MPC_THR_HOVER'))
