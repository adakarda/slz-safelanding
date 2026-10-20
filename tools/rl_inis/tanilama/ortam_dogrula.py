"""F1: replay the flight's commands through eland_rl.dynamics.Vehicle (the environment's own code)."""
import sys

import numpy as np

from eland_rl.dynamics import DynamicsParams, Vehicle

d = np.load(sys.argv[1])
lp, sp = d['lp'], d['sp']
t_sp = (sp[:, 0] - sp[0, 0]) * 1e-6
nz = np.argmax(np.abs(sp[:, 1:]).sum(1) > 0)
basla = t_sp[nz] - 4.0
# the env commands in ENU and z up; PX4 logs NED. Velocity is isotropic in xy, so N->x, E->y, D->-z is enough.
cmd = np.stack([sp[:, 1], sp[:, 2], -sp[:, 3]], 1)
t_lp = (lp[:, 0] - sp[0, 0]) * 1e-6
v_lp = np.stack([lp[:, 4], lp[:, 5], -lp[:, 6]], 1)

for ad, p in (('olculen varsayilan', DynamicsParams(latency_s=0.0, tilt_bias_deg=0.0)),
              ('eski varsayilan (gecikmesiz)', DynamicsParams(tau_xy=0.5, tau_z=0.5, a_max=3.0, cmd_delay_xy=0.0,
                                                               cmd_delay_z=0.0, latency_s=0.0, tilt_bias_deg=0.0))):
    veh = Vehicle(p, (0, 0, 25), 0.0)
    veh.vel = np.interp(basla, t_lp, v_lp[:, 0]), np.interp(basla, t_lp, v_lp[:, 1]), 0.0
    veh.vel = np.array(veh.vel, float)
    zaman, hiz = [], []
    t = basla
    while t < t_sp[-1] - 0.25:
        i = max(0, np.searchsorted(t_sp, t, side='right') - 1)
        veh.step(cmd[i], 0.05)
        t += 0.05
        zaman.append(t)
        hiz.append(veh.vel.copy())
    zaman, hiz = np.array(zaman) - basla, np.array(hiz)
    olc = np.stack([np.interp(zaman + basla, t_lp, v_lp[:, k]) for k in range(3)], 1)
    for bol, m in (('basamak', zaman < 56), ('rastgele', zaman >= 56)):
        exy = np.sqrt(((hiz[m, :2] - olc[m, :2]) ** 2).mean())
        ez = np.sqrt(((hiz[m, 2] - olc[m, 2]) ** 2).mean())
        print(f'{ad}, {bol}: RMSE xy {exy:.3f} m/s, z {ez:.3f} m/s')
