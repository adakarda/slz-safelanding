"""Bir ULog'daki vehicle_command ve vehicle_command_ack kayitlari + yerel konumun global referansi (xy_global)."""
import sys

from pyulog import ULog

u = ULog(sys.argv[1], message_name_filter_list=['vehicle_command', 'vehicle_command_ack', 'vehicle_local_position',
                                                'vehicle_status'])
d = {x.name: x.data for x in u.data_list}
t0 = u.start_timestamp
vc = d.get('vehicle_command', {})
for i in range(len(vc.get('timestamp', []))):
    print(f'cmd t {(int(vc["timestamp"][i]) - t0) / 1e6:7.1f} cmd {vc["command"][i]} p1 {vc["param1"][i]:.1f} p2 {vc["param2"][i]:.1f} '
          f'p5 {vc["param5"][i]:.6f} p6 {vc["param6"][i]:.6f} p7 {vc["param7"][i]:.1f} ext {vc["from_external"][i]}')
ack = d.get('vehicle_command_ack', {})
for i in range(len(ack.get('timestamp', []))):
    print(f'ack t {(int(ack["timestamp"][i]) - t0) / 1e6:7.1f} cmd {ack["command"][i]} sonuc {ack["result"][i]}')
lp = d['vehicle_local_position']
print('xy_global', set(lp['xy_global'].tolist()), 'z_global', set(lp['z_global'].tolist()),
      'ref_lat', lp['ref_lat'][-1], 'ref_lon', lp['ref_lon'][-1], 'ref_alt', lp['ref_alt'][-1])
vs = d['vehicle_status']
print('nav_state', sorted(set(vs['nav_state'].tolist())))
