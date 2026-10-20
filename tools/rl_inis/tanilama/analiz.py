"""F1: fit the light environment's dynamics to the identification flight.

Model (eland_rl.dynamics): first-order velocity response, tau_xy / tau_z,
horizontal acceleration capped at a_max, plus a pure command delay. Fitted by
grid search on the step programme and checked on the random-action part,
which the fit has not seen. Tilt is checked against atan(a_h / (g - a_z)).

    python3 analiz.py kos1.npz
"""
import sys

import numpy as np

G = 9.81
DT = 0.02


def yukle(yol):
    d = np.load(yol)
    lp, att, sp = d['lp'], d['att'], d['sp']
    t0 = sp[0, 0]
    t = np.arange(sp[0, 0], sp[-1, 0], DT * 1e6)
    v = np.stack([np.interp(t, lp[:, 0], lp[:, k]) for k in (4, 5, 6)], 1)
    a = np.stack([np.interp(t, lp[:, 0], lp[:, k]) for k in (7, 8, 9)], 1)
    i = np.clip(np.searchsorted(sp[:, 0], t, side='right') - 1, 0, len(sp) - 1)
    cmd = sp[i, 1:4]
    q = np.stack([np.interp(t, att[:, 0], att[:, k]) for k in (1, 2, 3, 4)], 1)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    r33 = 1 - 2 * (q[:, 1] ** 2 + q[:, 2] ** 2)
    tilt = np.degrees(np.arccos(np.clip(r33, -1, 1)))
    return (t - t0) * 1e-6, v, a, cmd, tilt


def benzet_xy(cmd, v_olc, tau, amax, gec, bolme):
    """Horizontal model for every (tau, amax, gec) at once.

    Returns the RMSE against the measured velocity before and after index
    `bolme` (P each), and the trajectory when there is a single combination.
    """
    P, N = tau.size, cmd.shape[0]
    k = np.round(gec / DT).astype(int)
    v = np.tile(v_olc[0, :2], (P, 1)).astype(float)
    se = np.zeros((2, P))
    iz = np.empty((N, 2)) if P == 1 else None
    for n in range(N):
        c = cmd[np.maximum(n - k, 0), :2]
        acc = (c - v) / tau[:, None]
        nrm = np.hypot(acc[:, 0], acc[:, 1])
        s = np.where(nrm > amax, amax / np.maximum(nrm, 1e-9), 1.0)
        v = v + acc * s[:, None] * DT
        se[int(n >= bolme)] += ((v - v_olc[n, :2]) ** 2).sum(1)
        if iz is not None:
            iz[n] = v[0]
    rmse = np.sqrt(se / (2 * np.array([[bolme], [N - bolme]])))
    return rmse[0], rmse[1], iz


def benzet_z(cmd, v_olc, tau, gec, bolme):
    P, N = tau.size, cmd.shape[0]
    k = np.round(gec / DT).astype(int)
    v = np.full(P, v_olc[0, 2], float)
    se = np.zeros((2, P))
    iz = np.empty(N) if P == 1 else None
    for n in range(N):
        c = cmd[np.maximum(n - k, 0), 2]
        v = v + (c - v) / tau * DT
        se[int(n >= bolme)] += (v - v_olc[n, 2]) ** 2
        if iz is not None:
            iz[n] = v[0]
    rmse = np.sqrt(se / np.array([[bolme], [N - bolme]]))
    return rmse[0], rmse[1], iz


def main(yol):
    t, v, a, cmd, tilt = yukle(yol)
    # the log starts with the 2 s offboard warm-up; the programme starts 4 s before its first non-zero command
    t0 = t[np.argmax(np.abs(cmd).sum(1) > 0)] - 4.0
    t = t - t0
    rnd = np.argmax(t >= 56.0)               # programme(): 56 s of steps, then random actions
    print(f'kayit {t[-1]:.1f} s (sim, program basi 0), basamak bolumu 0-{t[rnd]:.0f} s, '
          f'rastgele bolum {t[rnd]:.0f}-{t[-1]:.0f} s')

    tau_g, amax_g, gec_g = np.meshgrid(np.arange(0.1, 2.01, 0.05), np.arange(0.5, 8.01, 0.25),
                                       np.arange(0.0, 0.301, 0.02), indexing='ij')
    tau_g, amax_g, gec_g = tau_g.ravel(), amax_g.ravel(), gec_g.ravel()
    e_bas, e_rnd, _ = benzet_xy(cmd, v, tau_g, amax_g, gec_g, rnd)
    i = int(np.argmin(e_bas))
    print(f'XY uydurma (basamaklar): tau_xy {tau_g[i]:.2f} s, a_max {amax_g[i]:.2f} m/s2, gecikme {gec_g[i]:.2f} s, '
          f'RMSE {e_bas[i]:.3f} m/s; ayni parametre rastgele bolumde RMSE {e_rnd[i]:.3f} m/s')
    i2 = int(np.argmin(e_rnd))
    print(f'  (karsilastirma: rastgele bolume uydurulsaydi tau_xy {tau_g[i2]:.2f}, a_max {amax_g[i2]:.2f}, '
          f'gecikme {gec_g[i2]:.2f}, RMSE {e_rnd[i2]:.3f})')
    n_b, n_r = rnd, len(t) - rnd
    e_tum = np.sqrt((e_bas ** 2 * n_b + e_rnd ** 2 * n_r) / (n_b + n_r))
    i3 = int(np.argmin(e_tum))
    print(f'  (tum kayda uydurulsaydi tau_xy {tau_g[i3]:.2f}, a_max {amax_g[i3]:.2f}, gecikme {gec_g[i3]:.2f}; '
          f'RMSE basamak {e_bas[i3]:.3f}, rastgele {e_rnd[i3]:.3f}, tum {e_tum[i3]:.3f})')
    print(f'  (rastgele uydurmasi basamaklarda RMSE {e_bas[i2]:.3f})')
    j = int(np.argmin(np.abs(tau_g - 0.5) + np.abs(amax_g - 3.0) + np.abs(gec_g)))
    print(f'  ortamin varsayilani (0.5 s, 3.0, 0): basamak RMSE {e_bas[j]:.3f}, rastgele RMSE {e_rnd[j]:.3f} m/s')
    _, _, sim_iz = benzet_xy(cmd, v, tau_g[i:i + 1], amax_g[i:i + 1], gec_g[i:i + 1], rnd)

    tz, gz = np.meshgrid(np.arange(0.1, 2.01, 0.05), np.arange(0.0, 0.301, 0.02), indexing='ij')
    tz, gz = tz.ravel(), gz.ravel()
    ez, ezr, _ = benzet_z(cmd, v, tz, gz, rnd)
    k = int(np.argmin(ez))
    print(f'Z uydurma: tau_z {tz[k]:.2f} s, gecikme {gz[k]:.2f} s, RMSE {ez[k]:.3f} m/s; rastgele bolumde {ezr[k]:.3f} m/s')
    k2 = int(np.argmin(ezr))
    print(f'  (rastgele bolume uydurulsaydi tau_z {tz[k2]:.2f}, gecikme {gz[k2]:.2f}, RMSE {ezr[k2]:.3f}; '
          f'basamakta {ez[k2]:.3f})')
    hover = (t > 0.5) & (t < 3.5)
    print(f'hover egimi (0.5-3.5 s): ort {tilt[hover].mean():.2f} deg')
    _, _, sz_iz = benzet_z(cmd, v, tz[k:k + 1], gz[k:k + 1], rnd)

    ah = np.hypot(a[:, 0], a[:, 1])
    beklenen = np.degrees(np.arctan2(ah, np.maximum(G - a[:, 2], 1.0)))
    egim = np.polyfit(beklenen, tilt, 1)
    print(f'egim: olculen en cok {tilt.max():.1f} deg (p95 {np.percentile(tilt, 95):.1f}); '
          f'olculen = {egim[0]:.2f} x atan(a/g) + {egim[1]:.2f} deg; korelasyon {np.corrcoef(beklenen, tilt)[0, 1]:.3f}')
    print(f'yatay ivme: en cok {ah.max():.2f} m/s2, p95 {np.percentile(ah, 95):.2f} m/s2')
    for ad, sl in (('+N 1 m/s', (4.0, 9.0)), ('+E 1 m/s', (22.0, 27.0)), ('asagi 2 m/s', (49.0, 52.0))):
        m = (t >= sl[0] + 2.5) & (t < sl[1])
        print(f'  {ad}: ulasilan hiz {np.abs(v[m]).max(0).round(2).tolist()} (son {sl[1] - sl[0] - 2.5:.1f} s)')

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        f, ax = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
        for n, ad in enumerate(('vN', 'vE')):
            ax[n].plot(t, cmd[:, n], 'k:', lw=1, label='komut')
            ax[n].plot(t, v[:, n], lw=1.2, label='PX4 (olculen)')
            ax[n].plot(t, sim_iz[:, n], lw=1, label='model')
            ax[n].set_ylabel(f'{ad} [m/s]')
        ax[2].plot(t, cmd[:, 2], 'k:', lw=1)
        ax[2].plot(t, v[:, 2], lw=1.2)
        ax[2].plot(t, sz_iz, lw=1)
        ax[2].set_ylabel('vD [m/s]')
        ax[3].plot(t, tilt, lw=1.2, label='olculen egim')
        ax[3].plot(t, beklenen, lw=1, label='atan(a_h/g)')
        ax[3].set_ylabel('egim [deg]')
        ax[3].set_xlabel('sim zamani [s]')
        for x in ax:
            x.axvline(t[rnd], color='grey', lw=0.8)
            x.grid(alpha=0.3)
        ax[0].legend(loc='upper right')
        ax[3].legend(loc='upper right')
        png = yol.replace('.npz', '.png')
        f.tight_layout()
        f.savefig(png, dpi=110)
        print('grafik', png)
    except ImportError:
        pass


if __name__ == '__main__':
    main(sys.argv[1])
