#!/usr/bin/env python3
"""Episode recorder for the data-collection task (docs/VERI_TOPLAMA.md).

Listens only: it subscribes to topics that already exist and publishes
nothing, so it cannot change what the aircraft does. Every message is kept
with the simulation time it arrived at; the tables are built afterwards, so
resampling is deterministic and every value carries how old it was.

Ground truth and simulation time come straight from gz-transport, not through
a ROS bridge: ros_gz_bridge turns gz.msgs.Pose_V into a TFMessage with every
child_frame_id empty, which loses the one thing needed -- which pose is the
aircraft. Subscribed here, read-only:
    /world/<w>/clock              gz.msgs.Clock   (sim time)
    /world/<w>/dynamic_pose/info  gz.msgs.Pose_V  (~48 Hz, model pose in world)
GZ_IP must match the server's (run_sim uses 127.0.0.1).

Writes into <cikti>/: duzenli.csv, maske_olaylari.csv, karar_olaylari.csv,
durum_gecisleri.csv, ep_ozet.json, kosul.yaml, ep.mat, maskeler.npz.
Column meanings are in tools/veri/data_dictionary.md.
"""
import argparse
import csv
import json
import math
import os
import signal
import sys
import time

import numpy as np
import rclpy
import yaml
from eland_msgs.msg import LandingCandidate, LandingState
try:  # detector_node's mask-rate rho (publish_rho); absent in older builds
    from eland_msgs.msg import GoruntuKapsami
except ImportError:
    GoruntuKapsami = None
from px4_msgs.msg import (TrajectorySetpoint, VehicleAttitude,
                          VehicleLandDetected, VehicleLocalPosition,
                          VehicleStatus)
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from gz.msgs10.clock_pb2 import Clock as GzClock
from gz.msgs10.pose_v_pb2 import Pose_V
from gz.transport13 import Node as GzNode
from sensor_msgs.msg import Image
from std_msgs.msg import Float32

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import basari  # noqa: E402
import dunya as dunya_mod  # noqa: E402
import ozellik  # noqa: E402

BEST_EFFORT = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         durability=DurabilityPolicy.VOLATILE,
                         history=HistoryPolicy.KEEP_LAST, depth=50)
RELIABLE = QoSProfile(reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.VOLATILE,
                      history=HistoryPolicy.KEEP_LAST, depth=50)

VALIDATE, COMMIT, HOLD, ABORT = 2, 5, 3, 4
STATE_NAMES = {0: 'SEARCH', 1: 'APPROACH', 2: 'VALIDATE', 3: 'HOLD',
               4: 'ABORT', 5: 'COMMIT'}
GRID_DT = 0.02          # 50 Hz
#: Model origin height above the surface it rests on, measured 2026-10-03 on
#: the landed x500 (dynamic_pose z = -0.013 m on flat ground). Used only when
#: the episode does not start on the ground.
Z_DINLENME_VARSAYILAN = -0.013
#: Camera above the model origin (x500_seg_cam_down/model.sdf: seg_cam pose
#: 0 0 0.10).
KAMERA_Z = 0.10
TEMAS_ESIGI_M = 0.03    # ground truth height that counts as touching down
CANDIDATE_TIMEOUT_S = 3.0  # emergency_landing_mode candidate_timeout_s


def quat_to_euler(w, x, y, z):
    roll = math.atan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y))
    s = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(s)
    yaw = math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))
    return roll, pitch, yaw


def stamp_s(stamp) -> float:
    return stamp.sec + stamp.nanosec * 1e-9


class Kaydedici(Node):
    def __init__(self, a):
        super().__init__('veri_kaydedici')
        self.a = a
        self.clock = None             # (sim_s, monotonic)
        self.ev = {k: [] for k in ('lp', 'att', 'land', 'status', 'sp',
                                   'state', 'cand', 'gt', 'clock', 'vdis', 'rho')}
        self.masks = []               # (t_yakalama, t_alma, array)
        self.masks_bozuk = []
        self.t_start_mono = time.monotonic()
        self.landed_since = None
        self.saw_commit = False
        # Any descent: in W5's data-collection variant there is no COMMIT,
        # the aircraft touches the platform in VALIDATE.
        self.saw_descent = False
        self.done = False

        # gz-transport callbacks run on gz's own threads; they only append.
        self.gz = GzNode()
        w = a.gz_world
        if not self.gz.subscribe(GzClock, f'/world/{w}/clock', self.on_clock):
            self.get_logger().error(f'/world/{w}/clock dinlenemedi')
        if not self.gz.subscribe(Pose_V, f'/world/{w}/dynamic_pose/info', self.on_gt):
            self.get_logger().error(f'/world/{w}/dynamic_pose/info dinlenemedi')

        sub = self.create_subscription
        sub(VehicleLocalPosition, '/fmu/out/vehicle_local_position_v1',
            self.on_lp, BEST_EFFORT)
        sub(VehicleAttitude, '/fmu/out/vehicle_attitude', self.on_att, BEST_EFFORT)
        sub(VehicleLandDetected, '/fmu/out/vehicle_land_detected',
            self.on_land, BEST_EFFORT)
        sub(VehicleStatus, '/fmu/out/vehicle_status_v4', self.on_status,
            BEST_EFFORT)
        sub(TrajectorySetpoint, '/fmu/in/trajectory_setpoint', self.on_sp,
            BEST_EFFORT)
        sub(LandingState, '/eland/state', self.on_state, RELIABLE)
        sub(LandingCandidate, '/eland/candidate', self.on_cand, RELIABLE)
        sub(Image, a.mask_topic, self.on_mask, BEST_EFFORT)
        # The data-collection pattern, when one runs (tools/veri/politika.py).
        sub(Float32, '/eland/veri/v_ref',
            lambda m: self.ev['vdis'].append((self.t_gz(), float(m.data))), RELIABLE)
        if a.mask_bozuk_topic:
            sub(Image, a.mask_bozuk_topic, self.on_mask_bozuk, BEST_EFFORT)
        # rho at mask rate, only published when detector_node.publish_rho
        # is on: receive time, capture stamp, value.
        if GoruntuKapsami is not None:
            sub(GoruntuKapsami, '/eland/rho',
                lambda m: self.ev['rho'].append((self.t_gz(), stamp_s(m.header.stamp),
                                                 float(m.rho), float(m.view_bounded))),
                BEST_EFFORT)
        self.create_timer(0.5, self.check_stop)

    # -- time ------------------------------------------------------------
    def t_gz(self) -> float:
        """Simulation time now, from the last /clock plus wall time since."""
        if self.clock is None:
            return float('nan')
        s, m = self.clock
        return s + (time.monotonic() - m)

    def on_clock(self, msg):
        s = msg.sim.sec + msg.sim.nsec * 1e-9
        self.clock = (s, time.monotonic())
        self.ev['clock'].append((s, time.monotonic()))

    # -- inputs ------------------------------------------------------------
    def on_gt(self, msg):
        t_stamp = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
        for p in msg.pose:
            if p.name != self.a.model:
                continue
            q = p.orientation
            self.ev['gt'].append((t_stamp, self.t_gz(), p.position.x,
                                  p.position.y, p.position.z, q.w, q.x, q.y, q.z))
            break

    def on_lp(self, msg):
        self.ev['lp'].append((self.t_gz(), msg.x, msg.y, msg.z, msg.vx, msg.vy,
                              msg.vz, msg.heading, float(msg.dist_bottom_valid)))

    def on_att(self, msg):
        r, p, y = quat_to_euler(*[float(v) for v in msg.q])
        self.ev['att'].append((self.t_gz(), r, p, y))

    def on_land(self, msg):
        self.ev['land'].append((self.t_gz(), float(msg.landed),
                                float(msg.maybe_landed), float(msg.ground_contact)))
        if msg.landed:
            if self.landed_since is None:
                self.landed_since = time.monotonic()
        else:
            self.landed_since = None

    def on_status(self, msg):
        self.ev['status'].append((self.t_gz(), float(msg.nav_state),
                                  float(msg.arming_state)))

    def on_sp(self, msg):
        self.ev['sp'].append((self.t_gz(), float(msg.velocity[2]),
                              float(msg.position[2])))

    def on_state(self, msg):
        if msg.state == COMMIT:
            self.saw_commit = True
        if msg.state in (VALIDATE, COMMIT):
            self.saw_descent = True
        self.ev['state'].append((self.t_gz(), float(msg.state),
                                 float(msg.altitude_agl),
                                 float(msg.commanded_descent_mps),
                                 float(msg.descent_ceiling_mps),
                                 float(msg.area_ratio),
                                 float(msg.area_law_active), msg.reason))

    def on_cand(self, msg):
        self.ev['cand'].append((self.t_gz(), stamp_s(msg.header.stamp),
                                float(msg.valid), float(msg.candidate_id),
                                msg.position.x, msg.position.y, msg.radius,
                                msg.area_m2, msg.area_ratio,
                                float(msg.view_bounded), msg.risk_score))

    def _mask(self, msg, store):
        rows = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.step)
        store.append((stamp_s(msg.header.stamp), self.t_gz(),
                      rows[:, :msg.width].copy()))

    def on_mask(self, msg):
        self._mask(msg, self.masks)

    def on_mask_bozuk(self, msg):
        self._mask(msg, self.masks_bozuk)

    # -- stopping --------------------------------------------------------------
    def check_stop(self):
        if time.monotonic() - self.t_start_mono > self.a.sure:
            self.get_logger().info('kayit suresi doldu')
            self.done = True
        elif (self.a.inince_dur and (self.saw_commit or self.saw_descent)
              and self.landed_since
              and time.monotonic() - self.landed_since > 3.0):
            self.get_logger().info('inis algilandi, kayit bitiyor')
            self.done = True


# ---------------------------------------------------------------- tables
def arr(events, n):
    if not events:
        return np.full((0, n), np.nan)
    return np.array([e[:n] for e in events], dtype=float)


def hold(t_ev, v_ev, grid):
    """Zero-order hold of events onto the grid; returns (values, age_ms)."""
    t_ev, v_ev = np.asarray(t_ev, float), np.asarray(v_ev, float)
    keep = np.isfinite(t_ev)          # events before the first /clock have no time
    t_ev, v_ev = t_ev[keep], v_ev[keep]
    if len(t_ev) == 0:
        return np.full(len(grid), np.nan), np.full(len(grid), np.nan)
    order = np.argsort(t_ev, kind='stable')
    t_ev, v_ev = t_ev[order], v_ev[order]
    idx = np.searchsorted(t_ev, grid, side='right') - 1
    ok = idx >= 0
    vals = np.full(len(grid), np.nan)
    age = np.full(len(grid), np.nan)
    vals[ok] = v_ev[idx[ok]]
    age[ok] = (grid[ok] - t_ev[idx[ok]]) * 1000.0
    return vals, age


def continuity(name, t, nominal_hz=None):
    t = np.asarray([x for x in t if np.isfinite(x)])
    if len(t) < 3:
        return {'kanal': name, 'n': int(len(t))}
    t = np.sort(t)
    g = np.diff(t)
    med = float(np.median(g))
    ref = 1.0 / nominal_hz if nominal_hz else med
    return {
        'kanal': name, 'n': int(len(t)), 'hz': round(len(t) / (t[-1] - t[0]), 3),
        'aralik_ortanca_ms': round(med * 1000, 2),
        'aralik_en_uzun_ms': round(float(g.max()) * 1000, 2),
        'jitter_std_ms': round(float(g.std()) * 1000, 2),
        'bosluk_2x_sayisi': int((g > 2.0 * ref).sum()),
        'kayip_mesaj_tahmini': int(np.maximum(np.round(g / ref) - 1, 0)[g > 1.5 * ref].sum()),
    }


def write_csv(path, cols, data):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        n = len(data[cols[0]]) if cols else 0
        for i in range(n):
            row = []
            for c in cols:
                v = data[c][i]
                if isinstance(v, (float, np.floating)):
                    row.append('' if not np.isfinite(v) else f'{float(v):.6g}')
                else:
                    row.append(v)
            w.writerow(row)


def build(node, a):
    """Turn the event lists into the episode's tables and files."""
    ev = node.ev
    dw = dunya_mod.Dunya(a.dunya_yaml)
    out = a.cikti
    os.makedirs(out, exist_ok=True)
    meta = dict(ep_id=a.ep_id, dunya_id=a.dunya_id or dw.dunya_id,
                tohum=a.tohum, kol=a.kol)

    lp = arr(ev['lp'], 9)
    att = arr(ev['att'], 4)
    land = arr(ev['land'], 4)
    st_ = arr(ev['status'], 3)
    sp = arr(ev['sp'], 3)
    state = arr(ev['state'], 7)
    cand = arr(ev['cand'], 11)
    gt = arr(ev['gt'], 9)

    # Episode window: everything we have a simulation time for.
    tt = [x[:, 0] for x in (lp, att, state, gt) if len(x)]
    if not tt:
        raise RuntimeError('hic veri gelmedi -- kopruler ve sim calisiyor mu?')
    allt = np.concatenate(tt)
    allt = allt[np.isfinite(allt)]
    grid = np.arange(allt.min(), allt.max(), GRID_DT)

    # Ground truth: model pose in the world, heights from the world geometry.
    z_rest, z_rest_src = Z_DINLENME_VARSAYILAN, 'varsayilan (2026-10-03 olcumu)'
    if len(gt) and len(land) and land[0, 1] > 0.5:
        z_rest = float(gt[0, 4] - dw.yuzey_z(gt[0, 2], gt[0, 3]))
        z_rest_src = 'kayit basinda yerde olculdu'
    if len(gt):
        gx, gy, gz = gt[:, 2], gt[:, 3], gt[:, 4]
        zemin = np.array([dw.yuzey_z(x, y) for x, y in zip(gx, gy)])
        h_zemin = gz - zemin - z_rest
        h_hedef = gz - dw.hedef_z() - z_rest
        h_kamera = gz + KAMERA_Z - zemin
        tg = gt[:, 0]
        vz_gt = -np.gradient(gz, tg) if len(tg) > 2 else np.full(len(tg), np.nan)
    else:
        tg = np.array([])
        h_zemin = h_hedef = h_kamera = vz_gt = np.array([])

    # EKF local frame (NED, origin at the EKF origin) -> world (ENU): a
    # constant offset, measured as the median over the episode.
    off = None
    if len(gt) and len(lp):
        e_on_gt = np.interp(tg, lp[:, 0], lp[:, 2])   # east = lp.y
        n_on_gt = np.interp(tg, lp[:, 0], lp[:, 1])   # north = lp.x
        off = (float(np.median(gx - e_on_gt)), float(np.median(gy - n_on_gt)))

    d = {}
    d['ep_id'] = [a.ep_id] * len(grid)
    d['dunya_id'] = [meta['dunya_id']] * len(grid)
    d['tohum'] = [a.tohum] * len(grid)
    d['kol'] = [a.kol] * len(grid)
    d['t_gz'] = grid
    cols = ['ep_id', 'dunya_id', 'tohum', 'kol', 't_gz']
    age_cols = []

    def add(name, t_ev, v_ev):
        vals, age = hold(t_ev, v_ev, grid)
        d[name] = vals
        d[name + '_yas_ms'] = age
        cols.append(name)
        age_cols.append(name + '_yas_ms')

    def tv(x, i, sign=1.0):
        """(times, values) of column i, empty-safe."""
        if not len(x):
            return np.array([]), np.array([])
        return x[:, 0], sign * x[:, i]

    add('durum', *tv(state, 1))
    add('nav_state', *tv(st_, 1))
    add('h_ekf', *tv(lp, 3, -1.0))          # NED z -> height, up positive
    add('vz_ekf', *tv(lp, 6))               # NED, down positive
    add('vx', *tv(lp, 4))                   # NED north
    add('vy', *tv(lp, 5))                   # NED east
    add('roll', *tv(att, 1))
    add('pitch', *tv(att, 2))
    add('yaw', *tv(att, 3))
    add('v_cmd', *tv(sp, 1))                # TrajectorySetpoint.velocity[2], down positive
    add('v_ref', *tv(state, 3))             # LandingState.commanded_descent_mps
    add('aktif_girdi', *tv(state, 6))       # 1 area law, 0 altitude fallback
    add('h_gercek_zemin', tg, h_zemin)
    add('h_gercek_hedef', tg, h_hedef)
    add('vz_gercek_hesap', tg, vz_gt)
    add('landed', *tv(land, 1))
    add('ground_contact', *tv(land, 3))
    add('v_ref_dis', *tv(arr(ev['vdis'], 2), 1))   # pattern sent, before the mode's clamp
    # Horizontal position: Gazebo truth (world ENU) and the EKF's (local NED),
    # for drift and for distances to the target.
    add('x_gercek', tg, gx if len(gt) else np.array([]))
    add('y_gercek', tg, gy if len(gt) else np.array([]))
    add('x_ekf_kuzey', *tv(lp, 1))
    add('y_ekf_dogu', *tv(lp, 2))

    # v_cmd only means something while the mode is sending velocity
    # setpoints (VALIDATE closed loop, COMMIT); elsewhere it is a stale value.
    in_descent = np.isin(d['durum'], (VALIDATE, COMMIT))
    d['v_cmd'] = np.where(in_descent & (d['v_cmd_yas_ms'] < 200.0), d['v_cmd'], np.nan)

    # Integral of the rate loop, reconstructed: u = v_ref + Kp*e + I. Only
    # where it is identifiable -- VALIDATE (COMMIT has no PI) and the output
    # not saturated.
    e = d['v_ref'] - d['vz_ekf']
    i_hesap = d['v_cmd'] - d['v_ref'] - a.kp * e
    ok = (d['durum'] == VALIDATE) & (d['v_cmd'] > 1e-3) & (d['v_cmd'] < a.vmax - 1e-3)
    d['I_hesap'] = np.where(ok, i_hesap, np.nan)
    cols.append('I_hesap')

    # Horizontal distance to the candidate published at that moment.
    if len(cand):
        valid = cand[:, 2] > 0.5
        ce, _ = hold(cand[valid, 0], cand[valid, 4], grid)
        cn, _ = hold(cand[valid, 0], cand[valid, 5], grid)
        pe, _ = hold(lp[:, 0], lp[:, 2], grid)
        pn, _ = hold(lp[:, 0], lp[:, 1], grid)
        d['yatay_hata_m'] = np.hypot(pe - ce, pn - cn)
    else:
        d['yatay_hata_m'] = np.full(len(grid), np.nan)
    cols.append('yatay_hata_m')
    if dw.hedef_merkez() and len(gt):
        mx, my = dw.hedef_merkez()
        gxe, _ = hold(tg, gx, grid)
        gyn, _ = hold(tg, gy, grid)
        d['yatay_hata_hedef_gercek_m'] = np.hypot(gxe - mx, gyn - my)
        cols.append('yatay_hata_hedef_gercek_m')

    all_cols = cols + age_cols
    write_csv(os.path.join(out, 'duzenli.csv'), all_cols, d)

    # -- mask events --------------------------------------------------------
    m_cols = ['t_yakalama', 't_alma', 'maske_yasi_ms'] + list(ozellik.FEATURE_COLUMNS) + \
        ['h_kamera_gercek', 'h_gercek_zemin', 'rho_hesap',
         'rho_temiz', 'rho_bozuk', 'view_bounded_bozuk', 't_alma_bozuk']
    md = {c: [] for c in m_cols}
    masks = node.masks
    bozuk = {round(t_cap, 4): (t_rx, m) for t_cap, t_rx, m in node.masks_bozuk}
    if masks:
        h_px, w_px = masks[0][2].shape
        k_fp = ozellik.footprint_factor(math.radians(a.hfov_deg), w_px, h_px)
        a_true = dw.hedef_alan()
        for t_cap, t_rx, m in masks:
            f = ozellik.features(m)
            md['t_yakalama'].append(t_cap)
            md['t_alma'].append(t_rx)
            md['maske_yasi_ms'].append((t_rx - t_cap) * 1000.0)
            for c in ozellik.FEATURE_COLUMNS:
                md[c].append(float(f[c]))
            hk = float(np.interp(t_cap, tg, h_kamera)) if len(tg) else float('nan')
            hz = float(np.interp(t_cap, tg, h_zemin)) if len(tg) else float('nan')
            md['h_kamera_gercek'].append(hk)
            md['h_gercek_zemin'].append(hz)
            md['rho_hesap'].append(a_true / (k_fp * hk * hk) if hk > 0 else float('nan'))
            # Clean and disturbed rho on the same row, matched by capture
            # stamp (the disturber keeps the stamp; a repeated frame carries
            # the new stamp over old content, which is the point).
            md['rho_temiz'].append(float(f['rho']))
            fb = bozuk.get(round(t_cap, 4))
            if fb is not None:
                fbz = ozellik.features(fb[1])
                md['rho_bozuk'].append(float(fbz['rho']))
                md['view_bounded_bozuk'].append(float(fbz['view_bounded']))
                md['t_alma_bozuk'].append(fb[0])
            else:
                md['rho_bozuk'].append(float('nan'))
                md['view_bounded_bozuk'].append(float('nan'))
                md['t_alma_bozuk'].append(float('nan'))
        for c in m_cols:
            md[c] = np.asarray(md[c], dtype=float)
    else:
        md = {c: np.array([]) for c in m_cols}
    write_csv(os.path.join(out, 'maske_olaylari.csv'), m_cols, md)
    if ev['rho']:
        r = np.array(ev['rho'], dtype=float)
        write_csv(os.path.join(out, 'rho_yayini.csv'),
                  ['t_alma', 't_yakalama', 'rho', 'view_bounded'],
                  {'t_alma': r[:, 0], 't_yakalama': r[:, 1], 'rho': r[:, 2],
                   'view_bounded': r[:, 3]})
    if masks and a.maske_kaydet:
        np.savez_compressed(os.path.join(out, 'maskeler.npz'),
                            maskeler=np.stack([m for _, _, m in masks]),
                            t_yakalama=md['t_yakalama'], t_alma=md['t_alma'])

    # -- decision events ----------------------------------------------------
    k_cols = ['t_alma', 't_damga', 'gecerli', 'aday_id', 'x_yerel', 'y_yerel',
              'radius_m', 'area_m2', 'area_ratio', 'view_bounded', 'risk',
              'secilen_nokta_hata_m']
    kd = {c: (cand[:, i] if len(cand) else np.array([])) for i, c in enumerate(k_cols[:-1])}
    if len(cand) and off is not None and dw.hedef_merkez():
        mx, my = dw.hedef_merkez()
        kd['secilen_nokta_hata_m'] = np.where(
            cand[:, 2] > 0.5, np.hypot(cand[:, 4] + off[0] - mx, cand[:, 5] + off[1] - my), np.nan)
    else:
        kd['secilen_nokta_hata_m'] = np.full(len(cand), np.nan)
    write_csv(os.path.join(out, 'karar_olaylari.csv'), k_cols, kd)

    # -- state transitions --------------------------------------------------
    g_rows = {'t_gz': [], 'onceki': [], 'sonraki': [], 'neden': []}
    prev = None
    for e_ in ev['state']:
        s = int(e_[1])
        if s != prev:
            g_rows['t_gz'].append(e_[0])
            g_rows['onceki'].append(STATE_NAMES.get(prev, '-') if prev is not None else '-')
            g_rows['sonraki'].append(STATE_NAMES.get(s, str(s)))
            g_rows['neden'].append(e_[7])
            prev = s
    write_csv(os.path.join(out, 'durum_gecisleri.csv'), list(g_rows), g_rows)

    # -- episode summary ------------------------------------------------------
    oz = dict(meta)
    oz['kayit_t_baslangic'] = float(grid[0]) if len(grid) else None
    oz['kayit_suresi_s'] = float(grid[-1] - grid[0]) if len(grid) > 1 else 0.0
    oz['z_dinlenme_m'] = z_rest
    oz['z_dinlenme_kaynak'] = z_rest_src
    oz['yerel_dunya_ofset_en_m'] = off
    # The mode engaging: nav_state entering 23 (EXTERNAL1) during the recording.
    t_mode = None
    prev_nav = None
    for e_ in ev['status']:
        if int(e_[1]) == 23 and prev_nav is not None and prev_nav != 23:
            t_mode = e_[0]
            break
        prev_nav = int(e_[1])
    t_val = next((e_[0] for e_ in ev['state'] if int(e_[1]) == VALIDATE), None)
    t_com = next((e_[0] for e_ in ev['state'] if int(e_[1]) == COMMIT), None)
    def rising(col, after):
        """First 0 -> 1 transition of a land-detector flag after `after`:
        an aircraft that is already on the ground when recording starts has
        not landed in this episode."""
        if after is None:
            return None
        prev = None
        for e_ in ev['land']:
            if e_[0] <= after:
                continue
            on = e_[col] > 0.5
            if prev is False and on:
                return e_[0]
            prev = on
        return None
    t_landed = rising(1, t_mode)
    t_gc = rising(3, min([t for t in (t_val, t_com) if t is not None], default=None))
    oz['t_mod_devrede'] = t_mode
    oz['t_validate'] = t_val
    oz['t_commit'] = t_com
    oz['t_px4_landed'] = t_landed
    oz['t_px4_ground_contact'] = t_gc
    oz['inis_suresi_mod_landed_s'] = (t_landed - t_mode) if (t_landed and t_mode) else None
    oz['alcalma_suresi_validate_landed_s'] = (t_landed - t_val) if (t_landed and t_val) else None
    # Touchdown from ground truth: first time after the highest point that the
    # model is within TEMAS_ESIGI_M of its resting height.
    t_temas = v_temas = None
    # From the first descent state: VALIDATE, or COMMIT straight from SEARCH
    # when the mode times out and descends blind (W1, negative islands).
    t_desc = min([t for t in (t_val, t_com) if t is not None], default=None)
    if len(tg) > 5 and t_desc:
        after = tg > t_desc
        below = after & (h_zemin < TEMAS_ESIGI_M)
        if below.any():
            i = int(np.argmax(below))
            t_temas = float(tg[i])
            win = (tg >= t_temas - 0.3) & (tg <= t_temas)
            v_temas = float(np.nanmax(vz_gt[win])) if win.any() else None
    oz['t_temas_gercek'] = t_temas
    oz['temas_dikey_hiz_gercek_hesap_mps'] = v_temas
    oz['ground_contact_gecikmesi_s'] = (t_gc - t_temas) if (t_gc and t_temas) else None
    oz['landed_gecikmesi_s'] = (t_landed - t_temas) if (t_landed and t_temas) else None
    if t_com is not None:
        oz['commit_h_ekf_m'] = float(np.interp(t_com, lp[:, 0], -lp[:, 3])) if len(lp) else None
        oz['commit_h_gercek_hedef_m'] = float(np.interp(t_com, tg, h_hedef)) if len(tg) else None
    states = [int(e_[1]) for e_ in ev['state']]
    trans = list(zip(g_rows['sonraki'], g_rows['neden']))
    oz['abort_sayisi'] = sum(1 for s, _ in trans if s == 'ABORT')
    oz['hold_sayisi'] = sum(1 for s, _ in trans if s == 'HOLD')
    oz['abort_hold_nedenleri'] = [f'{s}: {r}' for s, r in trans if s in ('ABORT', 'HOLD')]
    oz['kor_inis'] = any('BLIND' in str(e_[7]) for e_ in ev['state'])
    # Candidate loss: stretches with no valid candidate for longer than the
    # mode's candidate_timeout, while the mode was active.
    losses = []
    if len(cand) and t_mode:
        tv = cand[(cand[:, 2] > 0.5) & (cand[:, 0] >= t_mode), 0]
        t_end = t_com or (t_landed or float(grid[-1]))
        pts = np.concatenate([[t_mode], np.sort(tv), [t_end]])
        gaps = np.diff(pts)
        losses = [float(g) for g in gaps if g > CANDIDATE_TIMEOUT_S]
    oz['aday_kayip_sayisi'] = len(losses)
    oz['aday_kayip_toplam_s'] = float(sum(losses))
    oz['aday_kayip_en_uzun_s'] = float(max(losses)) if losses else 0.0
    # Success: PX4 says landed, not blind, and the touchdown point is on the
    # target surface (island worlds) or on a landable class (open field).
    inis = t_landed is not None
    yer_ok = None
    if t_temas is not None and len(gt):
        i = int(np.argmin(np.abs(tg - t_temas)))
        yer_ok = dw.hedefte_mi(float(gx[i]), float(gy[i]))
        if yer_ok is None and masks:
            j = int(np.argmin(np.abs(md['t_yakalama'] - t_temas)))
            # mask taken just before touchdown: is the image centre landable?
            yer_ok = int(md['merkez_sinif'][max(0, j - 1)]) in ozellik.SAFE_CLASSES
            oz['basari_olcutu'] = 'landed + kor degil + temas oncesi maske merkezi inilebilir sinif'
        else:
            oz['basari_olcutu'] = 'landed + kor degil + temas noktasi hedef yuzeyde'
    oz['temas_yeri_uygun'] = yer_ok
    oz['basarili'] = bool(inis and not oz['kor_inis'] and bool(yer_ok))
    # and two levels of it by touchdown speed, < 0.5 and < 1.0 m/s
    oz.update(basari.temas_seviyeleri(oz))
    oz['sureklilik'] = [
        continuity('vehicle_local_position', lp[:, 0] if len(lp) else []),
        continuity('vehicle_attitude', att[:, 0] if len(att) else []),
        continuity('trajectory_setpoint', sp[:, 0] if len(sp) else []),
        continuity('eland_state', state[:, 0] if len(state) else []),
        continuity('eland_candidate', cand[:, 0] if len(cand) else []),
        continuity('gt_pose (damga)', tg),
        continuity('maske (yakalama damgasi)', md['t_yakalama'] if masks else [],
                   nominal_hz=a.kamera_hz),
        continuity('maske (alma)', md['t_alma'] if masks else [], nominal_hz=a.kamera_hz),
        continuity('clock', [c[0] for c in ev['clock']]),
    ]
    stamps = md['t_yakalama'] if masks else np.array([])
    oz['maske_damga_geri_gitme'] = int((np.diff(stamps) < 0).sum()) if len(stamps) > 1 else 0
    clk = np.array([c[0] for c in ev['clock']])
    oz['clock_geri_gitme'] = int((np.diff(clk) < 0).sum()) if len(clk) > 1 else 0
    # messages received on /eland/rho (0 when detector_node.publish_rho is off)
    oz['rho_yayini_sayisi'] = len(ev['rho'])
    with open(os.path.join(out, 'ep_ozet.json'), 'w') as f:
        json.dump(oz, f, indent=2, ensure_ascii=False, default=float)

    kosul = dict(meta, dunya_yaml=a.dunya_yaml, model=a.model, kp=a.kp,
                 vmax=a.vmax, hfov_deg=a.hfov_deg, ek=a.ek or {})
    if not os.path.exists(os.path.join(out, 'kosul.yaml')):
        with open(os.path.join(out, 'kosul.yaml'), 'w') as f:
            yaml.safe_dump(kosul, f, allow_unicode=True, sort_keys=False)

    # MATLAB: one struct per table, columns as fields (v7 = v5 format +
    # compression, which scipy writes and MATLAB reads with load()).
    try:
        import scipy.io
        def numeric(tab):
            return {k: (np.asarray(v, dtype=float) if not isinstance(v, list)
                        else np.array(v, dtype=object)) for k, v in tab.items()}
        scipy.io.savemat(os.path.join(out, 'ep.mat'), {
            'duzenli': numeric({c: d[c] for c in all_cols}),
            'maske': numeric(md),
            'karar': numeric(kd),
            'gecis': {k: np.array(v, dtype=object) if k != 't_gz' else np.asarray(v, float)
                      for k, v in g_rows.items()},
            'ozet_json': json.dumps(oz, default=float),
        }, do_compression=True, long_field_names=True)
    except Exception as exc:  # noqa: BLE001 -- CSVs are already written
        print(f'.mat yazilamadi: {exc}', file=sys.stderr)
    return oz


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--cikti', required=True)
    p.add_argument('--ep-id', default='ep')
    p.add_argument('--dunya-id', default='')
    p.add_argument('--dunya-yaml', default=None)
    p.add_argument('--tohum', type=int, default=-1)
    p.add_argument('--kol', default='kol0')
    p.add_argument('--model', default='x500_seg_cam_down_0')
    p.add_argument('--gz-world', default='eland_test')
    p.add_argument('--mask-topic', default='/eland/semantic_mask')
    p.add_argument('--mask-bozuk-topic', default='')
    p.add_argument('--sure', type=float, default=240.0, help='azami kayit, s (duvar)')
    p.add_argument('--inince-dur', action='store_true')
    p.add_argument('--maske-kaydet', action='store_true')
    p.add_argument('--kp', type=float, default=0.8)
    p.add_argument('--vmax', type=float, default=1.5)
    p.add_argument('--hfov-deg', type=float, default=99.7)
    p.add_argument('--kamera-hz', type=float, default=10.0)
    a = p.parse_args()
    a.ek = None

    rclpy.init()
    node = Kaydedici(a)

    def stop(*_):
        node.done = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.05)
    finally:
        oz = build(node, a)
        print(json.dumps({k: oz[k] for k in ('ep_id', 'kayit_suresi_s', 'basarili',
                                             'inis_suresi_mod_landed_s',
                                             'temas_dikey_hiz_gercek_hesap_mps')},
                         default=float))
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
