#!/usr/bin/env python3
"""Event and estimator log of one episode, next to kaydedici.py's files.

    tools/veri/sim_olay.py --cikti DIR --gz-world W

Writes, in DIR (kosu.sh points it at the episode folder):

  gozlemci.csv     every /eland/h_hat (YukseklikKaynagi): every height source,
                   the observer's state and gates, D, the real-time factor;
                   t_dugum_ns = the node's own (simulation) time of the estimate
  gozlemci_kare.csv every /eland/h_hat_kare row: what the observer consumed
                   at a descent start and at each frame (replay, E1)
  yasa_durumu.csv  every /eland/inis_yasasi_durumu (InisYasasiDurumu): selected
                   and active law, the height the law used, fallback, COMMIT
  olay.csv         t_gz, kaynak, olay, ayrinti -- one line per change:
                   parameter changes of the watched nodes (/parameter_events),
                   law changes, fallback start / end with its duration,
                   observer lock start / end with its duration, COMMIT entry
                   with the EKF and law heights, the capture stamp being
                   dropped, and the real-time factor every 5 s

t_gz is simulation time from Gazebo's clock, the same column kaydedici.py's
files have. Files are line-buffered and closed on SIGINT / SIGTERM, so the
last line is whole even when the episode is torn down. kaydedici.py is not
touched; the canli bozucu katmani (stage 2) will log here too.
"""
import argparse
import csv
import math
import os
import signal
import sys
import time

import rclpy
from eland_msgs.msg import InisYasasiDurumu, YukseklikKaynagi
from std_msgs.msg import Float64MultiArray
from gz.msgs10.clock_pb2 import Clock as GzClock
from gz.transport13 import Node as GzNode
from rcl_interfaces.msg import ParameterEvent
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy, qos_profile_parameter_events)

SENSOR = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE,
                    history=HistoryPolicy.KEEP_LAST, depth=10)
RELIABLE = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE,
                      history=HistoryPolicy.KEEP_LAST, depth=10)
IZLENEN = ('/emergency_landing_mode', '/yukseklik_gozlemci')


def alanlar(tip):
    return [k for k in tip.get_fields_and_field_types() if k != 'header']


def deger(v):
    # repr: the shortest text that reads back as the same double, so a replay
    # sees exactly what the node had (E1)
    if isinstance(v, float):
        return '' if math.isnan(v) else repr(v)
    if isinstance(v, bool):
        return int(v)
    return v


def param_deger(p):
    v = p.value
    return {1: v.bool_value, 2: v.integer_value, 3: v.double_value, 4: v.string_value}.get(v.type, '?')


class SimOlay(Node):
    def __init__(self, a):
        super().__init__('sim_olay')
        os.makedirs(a.cikti, exist_ok=True)
        self.dosyalar = []
        self.kapali = False
        self.k_gozlemci, self.f_gozlemci = self._csv(a.cikti, 'gozlemci.csv',
                                                     ['t_gz', 't_dugum_ns'] + alanlar(YukseklikKaynagi))
        self.k_kare, _ = self._csv(a.cikti, 'gozlemci_kare.csv', None)
        self.kare_baslik = None
        self.k_yasa, self.f_yasa = self._csv(a.cikti, 'yasa_durumu.csv',
                                             ['t_gz'] + alanlar(InisYasasiDurumu))
        self.k_olay, _ = self._csv(a.cikti, 'olay.csv', ['t_gz', 'kaynak', 'olay', 'ayrinti'])
        self.saat = None
        self.gz = GzNode()
        if not self.gz.subscribe(GzClock, f'/world/{a.gz_world}/clock', self.on_clock):
            self.get_logger().error(f'/world/{a.gz_world}/clock dinlenemedi')
        self.onceki_h = None
        self.onceki_y = None
        self.t_rtf = 0.0
        self.create_subscription(YukseklikKaynagi, '/eland/h_hat', self.on_h, SENSOR)
        self.create_subscription(Float64MultiArray, '/eland/h_hat_kare', self.on_kare, RELIABLE)
        self.create_subscription(InisYasasiDurumu, '/eland/inis_yasasi_durumu', self.on_yasa, RELIABLE)
        self.create_subscription(ParameterEvent, '/parameter_events', self.on_param,
                                 qos_profile_parameter_events)
        self.olay('sim_olay', 'basladi', a.cikti)

    def _csv(self, kok, ad, basliklar):
        f = open(os.path.join(kok, ad), 'w', newline='', buffering=1, encoding='utf-8')
        self.dosyalar.append(f)
        k = csv.writer(f)
        if basliklar is not None:
            k.writerow(basliklar)
        return k, f

    def kapat(self):
        """Once: the last event, then flush and close every file."""
        if self.kapali:
            return
        self.olay('sim_olay', 'bitti')
        self.kapali = True
        for f in self.dosyalar:
            try:
                f.flush()
                f.close()
            except OSError:
                pass

    # -- time ------------------------------------------------------------
    def on_clock(self, msg):
        self.saat = (msg.sim.sec + msg.sim.nsec * 1e-9, time.monotonic())

    def t_gz(self):
        if self.saat is None:
            return float('nan')
        s, m = self.saat
        return s + (time.monotonic() - m)

    def olay(self, kaynak, ad, ayrinti=''):
        self.k_olay.writerow([deger(self.t_gz()), kaynak, ad, ayrinti])

    # -- inputs ------------------------------------------------------------
    def on_h(self, m):
        ns = m.header.stamp.sec * 1000000000 + m.header.stamp.nanosec
        self.k_gozlemci.writerow([deger(self.t_gz()), ns] + [deger(getattr(m, k))
                                                             for k in alanlar(YukseklikKaynagi)])
        o = self.onceki_h
        if o is not None:
            if m.kilitli and not o.kilitli:
                self.olay('gozlemci', 'kilit_basladi', f'nu={m.nu:+.3f}')
            elif o.kilitli and not m.kilitli:
                self.olay('gozlemci', 'kilit_bitti', f'sure_s={o.kilit_suresi_s:.2f}')
            if o.damga_kullaniliyor and not m.damga_kullaniliyor:
                self.olay('gozlemci', 'damga_birakildi', 'saatler uyusmuyor')
            if m.gecerli and not o.gecerli:
                self.olay('gozlemci', 'baslatildi', f'tip={m.gozlemci_tipi} h_ekf={m.h_ekf_m:.2f} '
                          f'alan={m.alan_m2:.1f}')
        t = time.monotonic()
        if t - self.t_rtf >= 5.0 and not math.isnan(m.rtf):
            self.t_rtf = t
            self.olay('zaman', 'rtf', f'{m.rtf:.3f}')
        self.onceki_h = m

    def on_kare(self, m):
        if self.kare_baslik is None:
            self.kare_baslik = m.layout.dim[0].label.split(',') if m.layout.dim else []
            self.k_kare.writerow(['t_gz'] + self.kare_baslik)
        self.k_kare.writerow([deger(self.t_gz())] + [deger(float(v)) for v in m.data])

    def on_yasa(self, m):
        self.k_yasa.writerow([deger(self.t_gz())] + [deger(getattr(m, k))
                                                     for k in alanlar(InisYasasiDurumu)])
        o = self.onceki_y
        if o is None or m.aktif != o.aktif:
            self.olay('mod', 'yasa', f'secili={m.secili} aktif={m.aktif}')
        if o is not None:
            if m.yedekte and not o.yedekte:
                self.olay('mod', 'yedek_basladi', f'{m.yedek_nedeni}; fark_m={m.yedek_fark_m:.2f}')
                self.t_yedek = self.t_gz()
            elif o.yedekte and not m.yedekte:
                self.olay('mod', 'yedek_bitti',
                          f'sure_s={self.t_gz() - getattr(self, "t_yedek", float("nan")):.2f}')
            if m.kilitli and not o.kilitli:
                self.olay('mod', 'commit', f'yasa={m.aktif} h_yasa={m.commit_h_yasa_m:.2f} '
                          f'h_ekf={m.commit_h_ekf_m:.2f}')
        self.onceki_y = m

    def on_param(self, m):
        if m.node not in IZLENEN:
            return
        for p in list(m.new_parameters) + list(m.changed_parameters):
            self.olay('parametre', m.node.lstrip('/'), f'{p.name}={param_deger(p)}')


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--cikti', required=True)
    p.add_argument('--gz-world', required=True)
    a = p.parse_args()
    rclpy.init()
    node = SimOlay(a)

    def dur(*_):
        node.kapat()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, dur)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit, ExternalShutdownException):
        pass
    finally:
        node.kapat()
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:  # noqa: BLE001 -- already torn down
            pass
    sys.exit(0)


if __name__ == '__main__':
    main()
