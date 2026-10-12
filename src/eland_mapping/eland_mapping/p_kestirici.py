#!/usr/bin/env python3
"""p_kestirici -- where is the surface the aircraft is descending onto?

Read-only. It subscribes, computes and publishes on
/eland/yukseklik_kestirimi; it commands nothing, and the flight mode does not
listen to it. run_sim.sh starts it only with RUN_SIM_YUKSEKLIK=1, which also
switches detector_node.publish_rho on -- /eland/rho is its input.

Why it exists: the EKF height is measured from the take-off point. Over a
raised target (W5's 4 m platform) it reads 4 m too high all the way down, the
descent law slows for a ground that is not there, and the touchdown is hard
(1.47-1.49 m/s, measured). The camera does see the difference: the region
grows faster than the EKF's descent explains.

Each /eland/rho frame taken during the descent (VALIDATE or COMMIT), while the
safe region fits in view and the body is within ``en_cok_egiklik_deg`` of
level, adds a point (h_ekf, 1/sqrt(rho)). The line through them crosses zero
at the surface's height in the EKF frame, P, and its slope gives the region's
area; see p_hesap.py. When the region grows out of view the last trusted fit
is held -- which is when it matters, because the last metres are then flown
on h_ekf - P.
"""

import math
import time
from collections import deque

import rclpy
from rclpy.node import Node

from eland_common import px4_topics
from eland_common.qos import DECISION_QOS, PX4_QOS, SENSOR_QOS
from eland_mapping import p_hesap
from eland_msgs.msg import (GoruntuKapsami, LandingCandidate, LandingState,
                            YukseklikKestirimi)
from px4_msgs.msg import VehicleAttitude, VehicleLocalPosition

NAN = float('nan')
INIS = (LandingState.VALIDATE, LandingState.COMMIT)


class PKestirici(Node):

    def __init__(self) -> None:
        super().__init__('p_kestirici')
        p = self.declare_parameter
        p('rho_topic', '/eland/rho')
        p('cikis_topic', '/eland/yukseklik_kestirimi')
        p('state_topic', '/eland/state')
        p('candidate_topic', '/eland/candidate')
        # Only frames from the mode's own descent: during APPROACH the
        # aircraft moves sideways and the region under the centre is not yet
        # the target. False for hand-flown tests.
        p('yalniz_inis', True)
        # Above 5 deg the measured rho error grows from ~0.002 to 0.010-0.020
        # (Tur 3 D).
        p('en_cok_egiklik_deg', 5.0)
        p('rho_alt', 0.003)
        p('rho_ust', 0.98)
        # Mask capture to receipt, p50 measured 19.5 ms; the EKF height used
        # for a frame is moved back by this much at the current descent rate.
        p('gecikme_s', 0.02)
        # When a fit is trusted. 2 m of EKF descent: on the recorded W5
        # episodes (tools/veri/p_kestirimi.py, 2026-10-12) windows of 2.3 m
        # and more put P within 0.44 m of the truth, the two of 1.3 and 1.5 m
        # 0.74 and 1.19 m off.
        p('en_az_kare', 10)
        p('en_az_pencere_m', 2.0)
        p('en_cok_sigma_m', 0.5)
        p('en_cok_kare', 600)
        p('iraksama_kare', 5)
        # A candidate that jumps this far is another site: start over.
        p('aday_atlama_m', 3.0)

        g = lambda n: self.get_parameter(n).value  # noqa: E731
        self.yalniz_inis = bool(g('yalniz_inis'))
        self.egiklik_sinir = float(g('en_cok_egiklik_deg'))
        self.rho_alt, self.rho_ust = float(g('rho_alt')), float(g('rho_ust'))
        self.gecikme = float(g('gecikme_s'))
        self.en_az_kare = int(g('en_az_kare'))
        self.en_az_pencere = float(g('en_az_pencere_m'))
        self.en_cok_sigma = float(g('en_cok_sigma_m'))
        self.iraksama_kare = int(g('iraksama_kare'))
        self.aday_atlama = float(g('aday_atlama_m'))

        self.kareler = deque(maxlen=int(g('en_cok_kare')))   # (h, rho, t)
        self.son_gecerli = None
        self.inis = False
        self.aday_ref = None
        self.h = None
        self.v_asagi = 0.0
        self.egiklik = 0.0
        self.aday = None
        self.state = None

        self.pub = self.create_publisher(YukseklikKestirimi, g('cikis_topic'),
                                         SENSOR_QOS)
        self.create_subscription(GoruntuKapsami, g('rho_topic'), self.on_rho,
                                 SENSOR_QOS)
        self.create_subscription(VehicleLocalPosition,
                                 px4_topics.VEHICLE_LOCAL_POSITION, self.on_lp,
                                 PX4_QOS)
        self.create_subscription(VehicleAttitude, px4_topics.VEHICLE_ATTITUDE,
                                 self.on_att, PX4_QOS)
        self.create_subscription(LandingState, g('state_topic'), self.on_state,
                                 DECISION_QOS)
        self.create_subscription(LandingCandidate, g('candidate_topic'),
                                 self.on_cand, DECISION_QOS)
        self.create_timer(10.0, self.rapor)
        self.son_mesaj = None
        self.get_logger().info(
            f'p_kestirici up: {g("rho_topic")} -> {g("cikis_topic")}, '
            f'tilt < {self.egiklik_sinir:.0f} deg, trusted after '
            f'{self.en_az_kare} frames over {self.en_az_pencere:.1f} m')

    # ------------------------------------------------------------------
    def sifirla(self, neden):
        if self.kareler or self.son_gecerli is not None:
            self.get_logger().info(f'reset: {neden}')
        self.kareler.clear()
        self.son_gecerli = None
        self.aday_ref = None

    def on_lp(self, msg: VehicleLocalPosition) -> None:
        if msg.z_valid:
            self.h = -float(msg.z)
        if msg.v_z_valid:
            self.v_asagi = float(msg.vz)

    def on_att(self, msg: VehicleAttitude) -> None:
        q = msg.q
        self.egiklik = p_hesap.egiklik_deg(q[0], q[1], q[2], q[3])

    def on_state(self, msg: LandingState) -> None:
        self.state = msg.state
        inis = msg.state in INIS
        if inis and not self.inis:
            self.sifirla('descent started')
        self.inis = inis

    def on_cand(self, msg: LandingCandidate) -> None:
        if not msg.valid:
            return
        self.aday = msg
        pos = (msg.position.x, msg.position.y)
        if self.aday_ref is None:
            self.aday_ref = pos
        elif math.dist(pos, self.aday_ref) > self.aday_atlama:
            self.sifirla(f'candidate moved {math.dist(pos, self.aday_ref):.1f} m')
            self.aday_ref = pos

    # ------------------------------------------------------------------
    def on_rho(self, msg: GoruntuKapsami) -> None:
        out = YukseklikKestirimi()
        out.header = msg.header
        out.rho = float(msg.rho)
        out.view_bounded = bool(msg.view_bounded)
        out.egiklik_deg = float(self.egiklik)
        out.v_asagi_mps = float(self.v_asagi)
        h = (self.h + self.v_asagi * self.gecikme) if self.h is not None else NAN
        out.h_ekf_m = float(h)
        out.alan_harita_m2 = (float(self.aday.area_m2) if self.aday is not None
                              else NAN)

        aktif = self.inis or not self.yalniz_inis
        kullan = (aktif and self.h is not None and msg.view_bounded
                  and self.rho_alt < msg.rho < self.rho_ust
                  and self.egiklik < self.egiklik_sinir)
        out.kullanildi = bool(kullan)
        if kullan:
            self.kareler.append((h, float(msg.rho), time.monotonic()))

        hs = [k[0] for k in self.kareler]
        out.kare_sayisi = len(self.kareler)
        out.pencere_m = float(max(hs) - min(hs)) if hs else 0.0
        fit = p_hesap.kestir(hs, [k[1] for k in self.kareler]) if len(hs) >= 3 else None
        guvenilir = (fit is not None and math.isfinite(fit['p'])
                     and len(hs) >= self.en_az_kare
                     and out.pencere_m >= self.en_az_pencere
                     and fit['p_sigma'] <= self.en_cok_sigma)
        if guvenilir and kullan:
            self.son_gecerli = dict(fit, pencere=out.pencere_m, kare=len(hs))

        if kullan and guvenilir:
            out.durum, sonuc = YukseklikKestirimi.GECERLI, fit
        elif not kullan and self.son_gecerli is not None:
            out.durum, sonuc = YukseklikKestirimi.DONMUS, self.son_gecerli
        elif self.kareler:
            out.durum, sonuc = YukseklikKestirimi.TOPLANIYOR, fit
        else:
            out.durum, sonuc = YukseklikKestirimi.VERI_YOK, None

        if sonuc is not None:
            out.kullanilan_kare = int(sonuc['kullanilan'])
            out.p_m = float(sonuc['p'])
            out.p_sigma_m = float(sonuc['p_sigma'])
            out.alan_m2 = float(sonuc['alan'])
            out.artik_rms = float(sonuc['artik_rms'])
        else:
            out.p_m = out.p_sigma_m = out.alan_m2 = out.artik_rms = NAN
        out.h_hedef_m = float(h - out.p_m) if math.isfinite(out.p_m) else NAN

        son = [k for k in self.kareler][-self.iraksama_kare:]
        out.iraksama_1ps = (p_hesap.iraksama([k[2] for k in son], [k[1] for k in son])
                            if kullan and len(son) >= 3 else NAN)
        out.temas_suresi_s = (float(out.h_hedef_m / self.v_asagi)
                              if math.isfinite(out.h_hedef_m) and self.v_asagi > 0.05
                              and out.h_hedef_m > 0 else NAN)
        self.pub.publish(out)
        self.son_mesaj = out

    def rapor(self) -> None:
        m = self.son_mesaj
        if m is None:
            self.get_logger().info('no /eland/rho yet (detector_node.publish_rho on?)')
            return
        ad = {0: 'VERI_YOK', 1: 'TOPLANIYOR', 2: 'GECERLI', 3: 'DONMUS'}[m.durum]
        self.get_logger().info(
            f'{ad}: {m.kare_sayisi} frames over {m.pencere_m:.1f} m, '
            f'P {m.p_m:+.2f} +- {m.p_sigma_m:.2f} m, A {m.alan_m2:.0f} m2 '
            f'(map {m.alan_harita_m2:.0f}), h_ekf {m.h_ekf_m:.2f}, '
            f'to surface {m.h_hedef_m:.2f} m')


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PKestirici()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
