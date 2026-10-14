#!/usr/bin/env python3
"""yukseklik_gozlemci -- every height the descent law can be switched to.

Publishes /eland/h_hat (eland_msgs/YukseklikKaynagi, 50 Hz) for eland_mode's
``inis_yasasi``. It commands nothing; the mode reads it only with
``inis_yasasi_secimi: true``. run_sim.sh starts it with RUN_SIM_INIS_YASASI=1,
which also switches detector_node.publish_rho on (/eland/rho is its input).

Sources, all in the mode's convention (0 at rest on the surface below):
  h_ekf       -z of the EKF; measured from the take-off point
  h_gozlemci  gozlem_hesap.Sabit or .Kalman (gozlemci_tipi)
  h_dogrudan  gozlem_hesap.Dogrudan: sqrt(A0 / (4.216 rho)), A0 frozen
  h_kahin     Gazebo truth from tools/veri/gercek_yukseklik.py (simulation only)
  h_lazer     the EKF's dist_bottom, only while it is valid

The estimators start when the mode's descent starts (VALIDATE, HOLD or COMMIT
entered from outside them), from the EKF height plus the camera offset and the
candidate's area, and stop when it ends.

Clocks. This node runs on simulation time (use_sim_time; the launch file
bridges Gazebo's clock to /clock), the clock the mask's capture stamp is in, so
a frame is compared with the estimate as it was at capture (ignoring the stamp
cost 2.4x the error with 0.2 s of delay, KONTROLCU_OLCUMLERI.md §4.8). The EKF
values are the latest received, sampled on this clock. The real-time factor
(simulation seconds per wall second) is published with every estimate.

Replay record (2026-10-15, E1; recording only). Every input the estimators
consume goes out on /eland/h_hat_kare (std_msgs/Float64MultiArray, layout
KARE_ALANLARI, names in layout.dim[0].label): one row when a descent starts
and one per /eland/rho frame, with the node time, the stamp and every value
used. With the 50 Hz /eland/h_hat stamps and their vz, that is the whole input
sequence: tools/veri/gozlemci_esitlik.py replays it through gozlem_hesap and
compares with what was published.
"""

import math
import time
from collections import deque

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float32, Float64MultiArray, MultiArrayDimension

from eland_common import px4_topics
from eland_common.qos import DECISION_QOS, PX4_QOS, SENSOR_QOS
from eland_mapping import gozlem_hesap as G
from eland_mapping import p_hesap
from eland_msgs.msg import (GoruntuKapsami, LandingCandidate, LandingState,
                            YukseklikKaynagi)
from px4_msgs.msg import VehicleAttitude, VehicleLocalPosition

NAN = float('nan')
INIS = (LandingState.VALIDATE, LandingState.HOLD, LandingState.COMMIT)
# /eland/h_hat_kare row; tur 0 = descent start, 1 = /eland/rho frame. Unused
# fields NaN. x_*, c_g after the row was applied; tick_sayisi = /eland/h_hat
# messages published before it (orders a frame against the ticks).
KARE_ALANLARI = ('tur', 't_dugum', 't_yakalama', 'rho', 'view_bounded', 'egiklik_deg',
                 'v_asagi', 'h_ekf', 'h0_kamera', 'alan0', 'kapi_g', 'kapi_d', 'nu_g',
                 'x_g', 'c_g', 'x_d', 'damga', 'tick_sayisi')
# A capture stamp further than this from the node's clock means the two are not
# the same clock (use_sim_time off): the stamp is then ignored, and said once.
SAAT_UYUMSUZ_S = 5.0


class YukseklikGozlemci(Node):

    def __init__(self) -> None:
        super().__init__('yukseklik_gozlemci')
        p = self.declare_parameter
        p('rho_topic', '/eland/rho')
        p('cikis_topic', '/eland/h_hat')
        p('state_topic', '/eland/state')
        p('candidate_topic', '/eland/candidate')
        p('kahin_topic', '/eland/sim/h_gercek')
        p('yayin_hz', 50.0)
        p('gozlemci_tipi', 'sabit')
        p('kx', 2.0)
        p('kc', -2.0)
        p('sigma_olcum', 0.05)
        p('sigma_x0', 0.7)
        p('sigma_c0', 0.7)
        p('rho_doyum', 0.75)
        p('nu_max', 0.5)
        p('sinirli_kapi', True)
        p('egiklik_kapi_deg', 5.0)
        p('kamera_ofseti_m', 0.09)
        p('kilit_kare', 10)
        p('kahin_bayat_s', 0.5)
        p('lazer_ofseti_m', 0.0)

        g = lambda n: self.get_parameter(n).value  # noqa: E731
        self.ofset = float(g('kamera_ofseti_m'))
        self.kahin_bayat = float(g('kahin_bayat_s'))
        self.lazer_ofset = float(g('lazer_ofseti_m'))
        if g('gozlemci_tipi') not in ('sabit', 'kalman'):
            raise SystemExit('yukseklik_gozlemci: gozlemci_tipi sabit | kalman olmali')
        ok, neden = G.kazanc_gecerli(float(g('kx')), float(g('kc')))
        if not ok:
            raise SystemExit(f'yukseklik_gozlemci: {neden}')
        self.add_on_set_parameters_callback(self.parametre)

        self.gozlemci = None
        self.dogrudan = None
        self.inis = False
        self.h_ekf = None
        self.v_asagi = 0.0
        self.lazer = NAN
        self.egiklik = 0.0
        self.aday = None
        self.kahin = NAN
        self.t_kahin = None
        self.aykiri_art_arda = 0
        self.t_kilit = None
        self.damga = True
        self.saat = deque()          # (sim s, monotonic s) for the real-time factor
        self.son = None

        self.pub = self.create_publisher(YukseklikKaynagi, g('cikis_topic'), SENSOR_QOS)
        self.pub_kare = self.create_publisher(Float64MultiArray, '/eland/h_hat_kare', DECISION_QOS)
        self.n_tick = 0
        self.create_subscription(GoruntuKapsami, g('rho_topic'), self.on_rho, SENSOR_QOS)
        self.create_subscription(VehicleLocalPosition, px4_topics.VEHICLE_LOCAL_POSITION,
                                 self.on_lp, PX4_QOS)
        self.create_subscription(VehicleAttitude, px4_topics.VEHICLE_ATTITUDE,
                                 self.on_att, PX4_QOS)
        self.create_subscription(LandingState, g('state_topic'), self.on_state, DECISION_QOS)
        self.create_subscription(LandingCandidate, g('candidate_topic'), self.on_cand,
                                 DECISION_QOS)
        self.create_subscription(Float32, g('kahin_topic'), self.on_kahin, SENSOR_QOS)
        self.create_timer(1.0 / max(float(g('yayin_hz')), 1.0), self.yayinla)
        self.create_timer(10.0, self.rapor)
        self.get_logger().info(
            f'up: {g("gozlemci_tipi")} (Kx {g("kx")}, Kc {g("kc")}), {g("rho_topic")} -> '
            f'{g("cikis_topic")}, use_sim_time {self.get_parameter("use_sim_time").value}')

    # ---------------------------------------------------------- parameters
    def parametre(self, params):
        """Gains apply at once to a running Sabit; type and sigmas at the next descent."""
        kx = float(self.get_parameter('kx').value)
        kc = float(self.get_parameter('kc').value)
        for prm in params:
            if prm.name == 'kx':
                kx = float(prm.value)
            elif prm.name == 'kc':
                kc = float(prm.value)
            elif prm.name == 'gozlemci_tipi' and prm.value not in ('sabit', 'kalman'):
                return SetParametersResult(successful=False, reason='gozlemci_tipi: sabit | kalman')
            elif prm.name.startswith('sigma_') and not float(prm.value) > 0.0:
                return SetParametersResult(successful=False, reason=f'{prm.name} > 0 olmali')
        ok, neden = G.kazanc_gecerli(kx, kc)
        if not ok:
            return SetParametersResult(successful=False, reason=neden)
        if isinstance(self.gozlemci, G.Sabit):
            self.gozlemci.kx, self.gozlemci.kc = kx, kc
        return SetParametersResult(successful=True)

    def _kapilar(self):
        g = lambda n: self.get_parameter(n).value  # noqa: E731
        eg = float(g('egiklik_kapi_deg'))
        return G.Kapilar(rho_doyum=float(g('rho_doyum')), nu_max=float(g('nu_max')),
                         sinirli=bool(g('sinirli_kapi')), egiklik_deg=eg if eg > 0 else None)

    # ---------------------------------------------------------- inputs
    def _simdi(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_lp(self, msg: VehicleLocalPosition) -> None:
        if msg.z_valid:
            self.h_ekf = -float(msg.z)
        if msg.v_z_valid:
            self.v_asagi = float(msg.vz)
        self.lazer = (float(msg.dist_bottom) - self.lazer_ofset) if msg.dist_bottom_valid else NAN

    def on_att(self, msg: VehicleAttitude) -> None:
        q = msg.q
        self.egiklik = p_hesap.egiklik_deg(q[0], q[1], q[2], q[3])

    def on_cand(self, msg: LandingCandidate) -> None:
        if msg.valid and msg.area_m2 > 0.0:
            self.aday = msg

    def on_kahin(self, msg: Float32) -> None:
        self.kahin = float(msg.data)
        self.t_kahin = self._simdi()

    def on_state(self, msg: LandingState) -> None:
        inis = msg.state in INIS
        if inis and not self.inis:
            self.baslat()
        elif not inis and self.inis:
            self.gozlemci = self.dogrudan = None
            self.aykiri_art_arda, self.t_kilit = 0, None
        self.inis = inis

    def baslat(self) -> None:
        t = self._simdi()
        if self.h_ekf is None or self.aday is None or t <= 0.0:
            self.get_logger().warning('descent started without EKF height, candidate area or '
                                      'clock; no estimate this descent')
            return
        g = lambda n: self.get_parameter(n).value  # noqa: E731
        if g('gozlemci_tipi') == 'kalman':
            self.gozlemci = G.Kalman(sigma_olcum=float(g('sigma_olcum')),
                                     sigma_x0=float(g('sigma_x0')),
                                     sigma_c0=float(g('sigma_c0')), kapilar=self._kapilar())
        else:
            self.gozlemci = G.Sabit(kx=float(g('kx')), kc=float(g('kc')), kapilar=self._kapilar())
        self.dogrudan = G.Dogrudan(kapilar=self._kapilar())
        h0 = self.h_ekf + self.ofset
        alan0 = float(self.aday.area_m2)
        self.gozlemci.baslat(t, h0, alan0)
        self.dogrudan.baslat(t, h0, alan0)
        self.aykiri_art_arda, self.t_kilit = 0, None
        self._kare_yayinla(tur=0, t_dugum=t, h_ekf=self.h_ekf, h0_kamera=h0, alan0=alan0)
        self.get_logger().info(f'descent: {g("gozlemci_tipi")} from h_ekf {self.h_ekf:.2f} m, '
                               f'area {alan0:.0f} m2')

    def _ilerlet(self, t) -> None:
        for e in (self.gozlemci, self.dogrudan):
            if e is not None:
                e.ilerlet(t, self.v_asagi)

    def on_rho(self, msg: GoruntuKapsami) -> None:
        if self.gozlemci is None:
            return
        t = self._simdi()
        self._ilerlet(t)
        ty = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.damga and abs(t - ty) > SAAT_UYUMSUZ_S:
            self.damga = False
            self.get_logger().error(
                f'capture stamp {ty:.1f} s vs node clock {t:.1f} s: not the same clock '
                f'(use_sim_time / /clock?); frames are now compared with the estimate at arrival')
        k = self.gozlemci.olcum(ty, float(msg.rho), bool(msg.view_bounded), self.egiklik,
                                damga_kullan=self.damga)
        kd = self.dogrudan.olcum(ty, float(msg.rho), bool(msg.view_bounded), self.egiklik,
                                 damga_kullan=self.damga)
        self._kare_yayinla(tur=1, t_dugum=t, t_yakalama=ty, rho=float(msg.rho),
                           view_bounded=float(bool(msg.view_bounded)), egiklik_deg=self.egiklik,
                           v_asagi=self.v_asagi, h_ekf=self.h_ekf, kapi_g=k, kapi_d=kd,
                           nu_g=self.gozlemci.nu)
        if k == G.KAPI_AYKIRI:
            self.aykiri_art_arda += 1
            if (self.t_kilit is None
                    and self.aykiri_art_arda >= int(self.get_parameter('kilit_kare').value)):
                self.t_kilit = t
                self.get_logger().warning(
                    f'gozlemci kilitli: {self.aykiri_art_arda} kare ust uste aykiri '
                    f'(nu {self.gozlemci.nu:+.2f}); tahmin yalniz vz ile ilerliyor')
        elif k == 0:
            if self.t_kilit is not None:
                self.get_logger().warning(f'gozlemci kilidi acildi: {t - self.t_kilit:.1f} s surdu')
            self.aykiri_art_arda, self.t_kilit = 0, None

    # ---------------------------------------------------------- output
    def _rtf(self, t) -> float:
        m = time.monotonic()
        self.saat.append((t, m))
        while len(self.saat) > 2 and m - self.saat[0][1] > 2.0:
            self.saat.popleft()
        (t0, m0) = self.saat[0]
        return (t - t0) / (m - m0) if m - m0 > 0.5 else NAN

    def yayinla(self) -> None:
        simdi = self.get_clock().now()
        t = simdi.nanoseconds * 1e-9
        if t <= 0.0:
            return
        self._ilerlet(t)
        out = YukseklikKaynagi()
        out.header.stamp = simdi.to_msg()   # the time propagated to, exactly
        out.rtf = float(self._rtf(t))
        out.h_ekf_m = float(self.h_ekf) if self.h_ekf is not None else NAN
        out.v_asagi_mps = float(self.v_asagi)
        out.gozlemci_tipi = str(self.get_parameter('gozlemci_tipi').value)
        taze = self.t_kahin is not None and t - self.t_kahin <= self.kahin_bayat
        out.h_kahin_m = float(self.kahin) if taze else NAN
        out.h_lazer_m = float(self.lazer)
        e = self.gozlemci
        out.gecerli = e is not None and e.hazir
        if out.gecerli:
            out.h_gozlemci_m = float(e.h - self.ofset)
            out.x_hat, out.c_hat = float(e.x), float(e.c)
            out.alan_m2 = float(e.alan)
            out.nu = float(e.nu)
            out.sigma_h_m = float(e.sigma_h) if isinstance(e, G.Kalman) else NAN
            out.iraksama_1ps = float(self.v_asagi / max(e.h, 0.1))
            out.son_kapi = int(e.son_kapi)
            out.kullanilan_kare = int(e.kullanilan)
            s = e.kapi_sayac
            out.kapi_rho_yok, out.kapi_doyum = s[G.KAPI_RHO_YOK], s[G.KAPI_DOYUM]
            out.kapi_sinir, out.kapi_egiklik = s[G.KAPI_SINIR], s[G.KAPI_EGIKLIK]
            out.kapi_aykiri = s[G.KAPI_AYKIRI]
        else:
            out.h_gozlemci_m = out.x_hat = out.c_hat = out.alan_m2 = NAN
            out.nu = out.sigma_h_m = out.iraksama_1ps = NAN
        d = self.dogrudan
        out.h_dogrudan_m = float(d.h - self.ofset) if d is not None and d.hazir else NAN
        out.iraksama_kahin_1ps = (float(self.v_asagi / max(self.kahin + self.ofset, 0.1))
                                  if taze else NAN)
        out.kilitli = self.t_kilit is not None
        out.kilit_suresi_s = float(t - self.t_kilit) if self.t_kilit is not None else 0.0
        out.damga_kullaniliyor = bool(self.damga)
        self.pub.publish(out)
        self.son = out
        self.n_tick += 1

    def _kare_yayinla(self, **alan) -> None:
        g, d = self.gozlemci, self.dogrudan
        alan.setdefault('x_g', g.x if g is not None and g.hazir else NAN)
        alan.setdefault('c_g', g.c if g is not None and g.hazir else NAN)
        alan.setdefault('x_d', d.x if d is not None and d.hazir else NAN)
        alan.setdefault('damga', float(self.damga))
        alan.setdefault('tick_sayisi', float(self.n_tick))
        m = Float64MultiArray()
        m.layout.dim = [MultiArrayDimension(label=','.join(KARE_ALANLARI),
                                            size=len(KARE_ALANLARI), stride=len(KARE_ALANLARI))]
        m.data = [float(alan.get(k, NAN)) if alan.get(k) is not None else NAN for k in KARE_ALANLARI]
        self.pub_kare.publish(m)

    def rapor(self) -> None:
        m = self.son
        if m is None:
            self.get_logger().info('no estimate published yet (waiting for /clock?)')
            return
        if not m.gecerli:
            return
        self.get_logger().info(
            f'h: gozlemci {m.h_gozlemci_m:.2f}, ekf {m.h_ekf_m:.2f}, kahin {m.h_kahin_m:.2f}, '
            f'dogrudan {m.h_dogrudan_m:.2f} m; A {m.alan_m2:.0f} m2; {m.kullanilan_kare} kare; '
            f'kapi doyum/sinir/egik/aykiri {m.kapi_doyum}/{m.kapi_sinir}/{m.kapi_egiklik}/'
            f'{m.kapi_aykiri}; RTF {m.rtf:.2f}'
            + (f'; KILITLI {m.kilit_suresi_s:.1f} s' if m.kilitli else ''))


def main(args=None) -> None:
    rclpy.init(args=args)
    node = YukseklikGozlemci()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
