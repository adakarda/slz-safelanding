"""Two ULogs' initial parameters side by side: every parameter whose value differs.

    python3 ulg_fark.py GAZEBO.ulg AIRSIM.ulg
"""
import sys

from pyulog import ULog

a = ULog(sys.argv[1], message_name_filter_list=[], parse_header_only=True).initial_parameters
b = ULog(sys.argv[2], message_name_filter_list=[], parse_header_only=True).initial_parameters
skip = ('CAL_', 'COM_FLIGHT_UUID', 'LND_FLIGHT_T', 'COM_MODE', 'SENS_DPRES_OFF', 'SENS_BOARD_')
print(f'{"ad":22s} {"gazebo":>14s} {"airsim":>14s}')
for k in sorted(set(a) | set(b)):
    if k.startswith(skip):
        continue
    if a.get(k) != b.get(k):
        print(f'{k:22s} {str(a.get(k, "-")):>14s} {str(b.get(k, "-")):>14s}')
