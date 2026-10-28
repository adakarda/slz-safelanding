"""AirSim acil inis senaryosu, gorev ucusu ve harita (docs/airsim/SENARYO_PLANI.md, Arda 28.10).

run_airsim.sh kalkisi yapip "hazir" dedikten sonra calisir:
  1. rota noktalarini VEHICLE_CMD_DO_REPOSITION (192) ile sirayla gonderir (30 m, 4 m'ye gelince sonraki);
  2. rota boyunca katedilen yol acil inis mesafesine gelince RL Landing'i acar (/eland/rl/etkinlestir);
  3. inisi izler; arac disarm olunca ya da 5 s durunca sonucu yazar (sonuc.json);
  4. /eland/senaryo/harita: kusbakisi harita, rota, canli iz, kamera alani, acil inis ani, sonuc.

    source /opt/ros/jazzy/setup.bash; source ~/ros2_ws/install/setup.bash
    python3 senaryo_ucus.py SENARYO.json CIKTI_KLASORU
"""
import json
import math
import os
import sys
import time

import cv2
import numpy as np
import rclpy
from px4_msgs.msg import VehicleCommand, VehicleLocalPosition, VehicleStatus
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Bool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from senaryo_uret import Harita, rgb_harita  # noqa: E402

from eland_common import px4_topics  # noqa: E402
from eland_common.qos import PX4_QOS  # noqa: E402

SINIF_AD = {0: 'cim/toprak', 1: 'sert zemin', 2: 'bitki/yol', 3: 'yapi', 4: 'su', 5: 'arac', 6: 'insan', 7: 'yol'}
PANEL, YAKIN = 860, 4.0


class Senaryo(Node):
    def __init__(self, sen, out):
        super().__init__('senaryo_ucus')
        self.sen, self.out = sen, out
        self.dogma = np.array(sen['dogma'])
        self.rota = [np.array(p) for p in sen['rota']]
        self.yol = [self.dogma] + self.rota
        self.uz = [float(np.linalg.norm(b - a)) for a, b in zip(self.yol, self.yol[1:])]
        self.h = Harita()
        self.lp = self.st = None
        self.durum, self.wp, self.son_komut, self.tetik_t, self.tetik_say = 'bekle', 0, 0.0, None, 0
        self.iz, self.acil_xy, self.sonuc = [], None, None
        self.dur_bas = None
        self.cmd = self.create_publisher(VehicleCommand, '/fmu/in/vehicle_command', PX4_QOS)
        self.rl = self.create_publisher(Bool, '/eland/rl/etkinlestir', 10)
        self.img = self.create_publisher(Image, '/eland/senaryo/harita', 1)
        self.create_subscription(VehicleLocalPosition, px4_topics.VEHICLE_LOCAL_POSITION,
                                 lambda m: setattr(self, 'lp', m), PX4_QOS)
        self.create_subscription(VehicleStatus, '/fmu/out/vehicle_status_v4', lambda m: setattr(self, 'st', m), PX4_QOS)
        self._taban()
        self.create_timer(0.2, self.adim)
        self.create_timer(0.5, self.ciz)
        self.get_logger().info(f'senaryo {sen["ozet"]}: {len(self.rota)} nokta, acil inis {sen["acil_mesafe_m"]:.0f}. m')

    # ---------------------------------------------------------------- geometry
    def dunya(self):
        return self.dogma + np.array([self.lp.x, self.lp.y])

    def katedilen(self, p):
        """Distance along the route of the vehicle's projection on its current leg."""
        i = min(self.wp, len(self.uz) - 1)
        a, b = self.yol[i], self.yol[i + 1]
        f = float(np.clip(np.dot(p - a, b - a) / max(self.uz[i] ** 2, 1e-6), 0, 1))
        return sum(self.uz[:i]) + f * self.uz[i]

    def git(self, hedef_dunya):
        lo = hedef_dunya - self.dogma
        r = 6378137.0
        lat = self.lp.ref_lat + math.degrees(lo[0] / r)
        lon = self.lp.ref_lon + math.degrees(lo[1] / (r * math.cos(math.radians(self.lp.ref_lat))))
        m = VehicleCommand(command=192, param1=-1.0, param2=1.0, param4=float('nan'), param5=lat, param6=lon,
                           param7=float(self.lp.ref_alt + self.sen['irtifa']), target_system=1, target_component=1,
                           source_system=255, source_component=190, from_external=True)
        m.timestamp = self.get_clock().now().nanoseconds // 1000
        self.cmd.publish(m)
        self.son_komut = time.time()

    # ---------------------------------------------------------------- state machine
    def adim(self):
        if self.lp is None or self.st is None or not self.lp.xy_global:
            return
        p = self.dunya()
        if not self.iz or np.linalg.norm(p - self.iz[-1]) > 0.5:
            self.iz.append(p)
        alt = -self.lp.z
        if self.durum == 'bekle':
            if alt > self.sen['irtifa'] - 5:
                self.durum = 'rota'
                self.git(self.rota[0])
                self.get_logger().info('rota basladi')
        elif self.durum == 'rota':
            if self.katedilen(p) >= self.sen['acil_mesafe_m']:
                self.durum, self.tetik_t, self.acil_xy = 'acil', time.time(), p.copy()
                self.nav0 = self.st.nav_state
                self.get_logger().info(f'ACIL INIS: ({p[0]:.1f}, {p[1]:.1f}), {alt:.1f} m')
                self.rl.publish(Bool(data=True))
                self.tetik_say = 1
                return
            if np.linalg.norm(p - self.rota[self.wp]) < YAKIN and self.wp < len(self.rota) - 1:
                self.wp += 1
                self.git(self.rota[self.wp])
            elif time.time() - self.son_komut > 3.0:   # one best-effort message can be lost: send again
                self.git(self.rota[self.wp])
        elif self.durum == 'acil':
            if self.st.nav_state != self.nav0:
                self.durum = 'inis'
                self.get_logger().info(f'RL Landing secildi (nav_state {self.st.nav_state})')
            elif time.time() - self.tetik_t > self.tetik_say and self.tetik_say < 6:
                self.rl.publish(Bool(data=True))
                self.tetik_say += 1
        elif self.durum == 'inis':
            v = math.hypot(self.lp.vx, self.lp.vy) + abs(self.lp.vz)
            if self.st.arming_state != VehicleStatus.ARMING_STATE_ARMED:
                self.bitir(p, 'disarm')
            elif v < 0.1:
                self.dur_bas = self.dur_bas or time.time()
                if time.time() - self.dur_bas > 5.0:
                    self.bitir(p, 'durdu')
            else:
                self.dur_bas = None

    def bitir(self, p, neden):
        r, c = self.h.piksel(*p)
        s = int(self.h.sinif[r, c]) if 0 <= r < self.h.sinif.shape[0] and 0 <= c < self.h.sinif.shape[1] else 255
        self.sonuc = dict(senaryo=self.sen['ozet'], tohum=self.sen['tohum'], neden=neden,
                          sure_s=round(time.time() - self.tetik_t, 1), acil_nokta=[round(float(v), 1) for v in self.acil_xy],
                          inis=[round(float(v), 1) for v in p], sinif=s, sinif_ad=SINIF_AD.get(s, 'bilinmiyor'),
                          guvenli_zemin=s in (0, 1), zemin_kurali=bool(self.h.uygun[r, c]) if s != 255 else False,
                          kayma_m=round(float(np.linalg.norm(p - self.acil_xy)), 1))
        json.dump(self.sonuc, open(os.path.join(self.out, 'sonuc.json'), 'w'), indent=1)
        self.durum = 'bitti'
        self.get_logger().info(f'SONUC {json.dumps(self.sonuc, ensure_ascii=False)}')
        self.bitis = time.time()

    # ---------------------------------------------------------------- map panel
    def _taban(self):
        R = self.sen['r_merkez'] + 20
        self.r0, self.c0 = self.h.piksel(R, -R)
        r1, c1 = self.h.piksel(-R, R)
        kes = rgb_harita(self.h)[self.r0:r1, self.c0:c1]
        self.olcek = PANEL / kes.shape[1]
        self.taban = cv2.resize(kes, (PANEL, PANEL), interpolation=cv2.INTER_AREA)
        self.taban = (self.taban * 0.85).astype(np.uint8)
        pts = [self.px(q) for q in self.yol]
        cv2.circle(self.taban, self.px(np.zeros(2)), int(self.sen['r_merkez'] / self.h.res * self.olcek), (230, 230, 230), 1)
        cv2.polylines(self.taban, [np.array(pts, np.int32)], False, (0, 210, 255), 3, cv2.LINE_AA)
        for i, q in enumerate(pts):
            cv2.circle(self.taban, q, 11, (40, 40, 40) if i else (255, 140, 0), -1, cv2.LINE_AA)
            cv2.putText(self.taban, str(i) if i else 'D', (q[0] - 6, q[1] + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                        (255, 255, 255), 2, cv2.LINE_AA)

    def px(self, q):
        r, c = self.h.piksel(float(q[0]), float(q[1]))
        return int((c - self.c0) * self.olcek), int((r - self.r0) * self.olcek)

    def ciz(self):
        img = self.taban.copy()
        if len(self.iz) > 1:
            cv2.polylines(img, [np.array([self.px(q) for q in self.iz], np.int32)], False, (255, 255, 255), 2, cv2.LINE_AA)
        if self.lp is not None and self.lp.xy_global:
            p = self.dunya()
            alt = max(-self.lp.z, 0.0)
            yari = alt * math.tan(math.radians(99.7 / 2))         # gimbal camera: north-up footprint
            a, b = self.px(p + [yari, -yari]), self.px(p - [yari, -yari])
            cv2.rectangle(img, a, b, (255, 255, 0), 1, cv2.LINE_AA)
            q = self.px(p)
            hd = self.lp.heading
            ucu = (int(q[0] + 18 * math.sin(hd)), int(q[1] - 18 * math.cos(hd)))
            cv2.circle(img, q, 8, (0, 0, 0), -1, cv2.LINE_AA)
            cv2.circle(img, q, 6, (0, 255, 255), -1, cv2.LINE_AA)
            cv2.line(img, q, ucu, (0, 255, 255), 2, cv2.LINE_AA)
        if self.acil_xy is not None:
            cv2.drawMarker(img, self.px(self.acil_xy), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 30, 4)
        if self.sonuc:
            renk = (60, 200, 60) if self.sonuc['guvenli_zemin'] else (40, 40, 230)
            cv2.circle(img, self.px(self.sonuc['inis']), 14, renk, 3, cv2.LINE_AA)
        ust = np.full((60, PANEL, 3), 25, np.uint8)
        if self.durum in ('bekle',):
            yazi, renk = 'KALKIS', (230, 230, 230)
        elif self.durum == 'rota':
            yazi, renk = f'ROTA  nokta {self.wp + 1}/{len(self.rota)}', (0, 210, 255)
        elif self.durum in ('acil', 'inis'):
            yazi, renk = f'ACIL INIS  {time.time() - self.tetik_t:4.1f} s  (RL + v4)', (60, 60, 255)
        else:
            s = self.sonuc
            yazi = f'INDI: {s["sinif_ad"]}  {s["sure_s"]} s  ' + ('GUVENLI' if s['guvenli_zemin'] else 'GUVENSIZ')
            renk = (80, 220, 80) if s['guvenli_zemin'] else (60, 60, 255)
        cv2.putText(ust, yazi, (14, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, renk, 2, cv2.LINE_AA)
        if self.lp is not None:
            cv2.putText(ust, f'{max(-self.lp.z, 0):5.1f} m', (PANEL - 140, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (230, 230, 230), 2, cv2.LINE_AA)
        out = np.ascontiguousarray(np.vstack([ust, img]))
        m = Image(height=out.shape[0], width=out.shape[1], encoding='bgr8', step=out.shape[1] * 3)
        m.data = out.tobytes()
        self.img.publish(m)


def main():
    sen = json.load(open(sys.argv[1]))
    rclpy.init()
    n = Senaryo(sen, sys.argv[2])
    try:
        while rclpy.ok():
            rclpy.spin_once(n, timeout_sec=0.1)
            if n.durum == 'bitti' and time.time() - n.bitis > 10:
                break
    except KeyboardInterrupt:
        pass
    n.destroy_node()
    rclpy.try_shutdown()


if __name__ == '__main__':
    main()
