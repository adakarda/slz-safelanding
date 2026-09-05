#!/usr/bin/env python3
"""Score tracker_node against the simulator's ground truth.

Reports, for the two moving obstacles:
  - how often they are tracked at all
  - position error of the current estimate
  - prediction error at each horizon step, by comparing a prediction made at
    t for t+dt against the truth that actually arrived at t+dt

Truth is /eland/obstacle_truth, published by obstacle_driver: [vehicle, person].
Nothing in the flight pipeline subscribes to it.
"""
import math
import sys
import time
from collections import defaultdict

import numpy as np
import rclpy
from eland_msgs.msg import DynamicObstacleArray
from geometry_msgs.msg import PoseArray
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                       ReliabilityPolicy)
from sensor_msgs.msg import Image

SENSOR_QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                        durability=DurabilityPolicy.VOLATILE,
                        history=HistoryPolicy.KEEP_LAST, depth=1)

# obstacle_driver publishes vehicles first, then people. With
# vehicle_count=2 that puts the first person at index 2, not 1 -- scoring
# index 1 as a person compares a person estimate against a vehicle.
import os
VEHICLE_COUNT = int(os.environ.get("VEHICLES", "2"))
NAMES = {0: 'vehicle(truth)', VEHICLE_COUNT: 'person(truth)'}
CLASS_OF = {0: 5, VEHICLE_COUNT: 6}


class Scorer(Node):
    def __init__(self, duration):
        super().__init__('tracking_scorer')
        self.duration = duration
        self.truth_hist = []          # (t, [(x, y), (x, y)])
        self.pending = []             # (target_t, idx, dt, px, py)
        self.pos_err = defaultdict(list)
        self.pred_err = defaultdict(list)
        self.seen = defaultdict(int)
        self.frames = 0
        self.speed_est = defaultdict(list)
        self.speed_conf = defaultdict(list)   # only tracks with a real fit
        self.pos_err_conf = defaultdict(list)
        self.pred_err_conf = defaultdict(list)
        # Measurement 1: does the segmentation keep up with things that move,
        # and does it keep calling them the same thing? Rate is the "how
        # often"; the per-frame pixel counts are the "consistently as what".
        self.mask_times = []
        self.mask_class_px = defaultdict(list)
        self.mask_present = defaultdict(int)
        self.mask_frames = 0
        self.instant_times = []
        self.track_seen = defaultdict(int)
        self.track_moving = defaultdict(int)
        self.create_subscription(Image, '/eland/semantic_mask', self.on_mask,
                                 SENSOR_QOS)
        self.map_info = None
        self.miss_outside = defaultdict(int)
        self.miss_no_blob = defaultdict(int)
        self.miss_far = defaultdict(int)
        self.miss_far_d = defaultdict(list)
        self.miss_edge_m = defaultdict(list)
        # Is the speed underestimate an artefact of the object living near the
        # edge of the mapped ground? Every tracked frame, filed by how far the
        # truth was from that edge.
        self.speed_by_margin = defaultdict(list)
        self.create_subscription(OccupancyGrid, '/eland/ground_map_instant',
                                 self.on_instant, SENSOR_QOS)
        self.create_subscription(PoseArray, '/eland/obstacle_truth', self.on_truth, 10)
        self.create_subscription(DynamicObstacleArray, '/eland/dynamic_obstacles',
                                 self.on_obs, 10)
        self.t0 = time.time()
        self.create_timer(1.0, self.maybe_finish)

    def on_instant(self, msg):
        self.instant_times.append(time.time())
        i = msg.info
        self.map_info = (i.origin.position.x, i.origin.position.y,
                         i.width * i.resolution, i.height * i.resolution)

    def edge_margin(self, x, y):
        """Metres from (x, y) to the nearest edge of the mapped ground.

        Negative outside it. The tracker drops blobs touching the border on
        purpose -- their centroid is the centroid of the visible half -- so a
        vehicle within a metre of the edge is expected to be missing, not
        missed.
        """
        if self.map_info is None:
            return None
        ox, oy, w, h = self.map_info
        return min(x - ox, ox + w - x, y - oy, oy + h - y)

    def on_mask(self, msg):
        self.mask_times.append(time.time())
        self.mask_frames += 1
        buf = np.frombuffer(msg.data, dtype=np.uint8)
        if msg.encoding in ('rgb8', 'bgr8'):
            buf = buf.reshape(msg.height, msg.width, 3)[:, :, 0]
        else:
            buf = buf.reshape(msg.height, msg.width)
        for cid in np.unique(buf):
            self.mask_present[int(cid)] += 1
            self.mask_class_px[int(cid)].append(int((buf == cid).sum()))

    def on_truth(self, msg):
        t = time.time()
        pts = [(p.position.x, p.position.y) for p in msg.poses]
        self.truth_hist.append((t, pts))
        if len(self.truth_hist) > 4000:
            del self.truth_hist[:1000]
        self.resolve(t)

    def truth_at(self, t):
        if not self.truth_hist:
            return None
        best = min(self.truth_hist, key=lambda e: abs(e[0] - t))
        if abs(best[0] - t) > 0.4:
            return None
        return best[1]

    def on_obs(self, msg):
        # What the tracker believes exists at all, regardless of whether it
        # matches a truth pose. "never tracked" and "tracked but mismatched"
        # need different fixes.
        for o in msg.obstacles:
            self.track_seen[int(o.class_id)] += 1
            if o.speed >= 0.5:
                self.track_moving[int(o.class_id)] += 1
        t = time.time()
        truth = self.truth_at(t)
        if truth is None:
            return
        self.frames += 1
        for idx, (tx, ty) in enumerate(truth):
            if idx not in NAMES:
                continue
            cls = CLASS_OF[idx]
            margin = self.edge_margin(tx, ty)
            outside = margin is not None and margin <= 0.0
            cands = [o for o in msg.obstacles if o.class_id == cls]
            if not cands:
                if outside:
                    self.miss_outside[idx] += 1
                else:
                    self.miss_no_blob[idx] += 1
                    if margin is not None:
                        self.miss_edge_m[idx].append(margin)
                continue
            near = min(cands, key=lambda o: math.hypot(o.position.x - tx,
                                                       o.position.y - ty))
            d = math.hypot(near.position.x - tx, near.position.y - ty)
            # Beyond this the nearest same-class blob is a different object
            # (the world has parked vehicles and standing people too).
            if d > 6.0:
                if outside:
                    self.miss_outside[idx] += 1
                else:
                    self.miss_far[idx] += 1
                    self.miss_far_d[idx].append(d)
                    if margin is not None:
                        self.miss_edge_m[idx].append(margin)
                continue
            self.seen[idx] += 1
            if margin is not None:
                self.speed_by_margin[idx].append((margin, near.speed))
            self.pos_err[idx].append(d)
            self.speed_est[idx].append(near.speed)
            confident = near.confidence >= 0.5
            if confident:
                self.speed_conf[idx].append(near.speed)
                self.pos_err_conf[idx].append(d)
            for p, dt in zip(near.predicted, near.predicted_times):
                self.pending.append((t + dt, idx, round(dt, 1), p.x, p.y, confident))

    def resolve(self, now):
        still = []
        for entry in self.pending:
            target_t, idx, dt, px, py, confident = entry
            if target_t > now:
                still.append(entry)
                continue
            truth = self.truth_at(target_t)
            if truth is None or idx >= len(truth):
                continue
            tx, ty = truth[idx]
            err = math.hypot(px - tx, py - ty)
            self.pred_err[(idx, dt)].append(err)
            if confident:
                self.pred_err_conf[(idx, dt)].append(err)
        self.pending = still

    def maybe_finish(self):
        if time.time() - self.t0 < self.duration:
            return
        def rate(times):
            if len(times) < 2:
                return 0.0, 0.0
            gaps = np.diff(np.asarray(times))
            return len(times) / (times[-1] - times[0]), float(gaps.max())

        # How fast the obstacles actually move as the pipeline experiences
        # them. They are driven on sim time and every estimate here is stamped
        # in wall time, so this is the configured speed times the real-time
        # factor -- and without it, an estimator reading 0.9 m/s against a
        # configured 1.2 m/s looks broken when it is correct.
        if len(self.truth_hist) > 2:
            span = self.truth_hist[-1][0] - self.truth_hist[0][0]
            for idx, name in NAMES.items():
                dist = 0.0
                prev = None
                for _t, pts in self.truth_hist:
                    if idx < len(pts):
                        if prev is not None:
                            dist += math.hypot(pts[idx][0] - prev[0],
                                               pts[idx][1] - prev[1])
                        prev = pts[idx]
                if span > 0:
                    print(f'{name} moved at {dist / span:.2f} m/s in wall clock '
                          f'over {span:.0f} s of recording')

        hz, worst = rate(self.mask_times)
        ihz, iworst = rate(self.instant_times)
        print('\n=== segmentation under motion ===')
        print(f'/eland/semantic_mask: {self.mask_frames} frames, {hz:.2f} Hz, '
              f'longest gap {worst:.2f} s')
        print(f'/eland/ground_map_instant: {len(self.instant_times)} frames, '
              f'{ihz:.2f} Hz, longest gap {iworst:.2f} s')
        names = {0: 'safe-soft', 1: 'safe-hard', 2: 'terrain-hazard',
                 3: 'structure', 4: 'water', 5: 'vehicle-animal',
                 6: 'person', 7: 'unknown'}
        for cid in sorted(self.mask_class_px):
            name = names.get(cid, '?')
            px = self.mask_class_px[cid]
            if not px:
                print(f'class {cid} ({name}): never appeared in the mask')
                continue
            arr = np.asarray(px, dtype=float)
            print(f'class {cid} ({name}): present in '
                  f'{self.mask_present[cid]}/{self.mask_frames} frames '
                  f'({100.0 * self.mask_present[cid] / max(self.mask_frames, 1):.0f}%), '
                  f'{arr.mean():.0f} px mean, {arr.std():.0f} px std, '
                  f'min {arr.min():.0f}, max {arr.max():.0f}')

        print(f'\n=== tracking, {self.frames} obstacle frames matched to truth ===')
        for idx, name in NAMES.items():
            errs = self.pos_err[idx]
            if not errs:
                print(f'{name}: never tracked')
                continue
            spd = self.speed_est[idx]
            print(f'{name}: tracked in {self.seen[idx]}/{self.frames} frames, '
                  f'position error mean {sum(errs)/len(errs):.2f} m '
                  f'max {max(errs):.2f} m, '
                  f'estimated speed mean {sum(spd)/len(spd):.2f} m/s')
            cs, ce = self.speed_conf[idx], self.pos_err_conf[idx]
            if cs:
                print(f'{" "*len(name)}  confidence>=0.5 in {len(cs)} frames: '
                      f'speed mean {sum(cs)/len(cs):.2f} m/s, '
                      f'position error mean {sum(ce)/len(ce):.2f} m')
            else:
                print(f'{" "*len(name)}  never reached confidence 0.5')
        print('--- prediction error by horizon (all tracks / confident only) ---')
        for (idx, dt), errs in sorted(self.pred_err.items()):
            if not errs:
                continue
            conf = self.pred_err_conf.get((idx, dt), [])
            ctxt = (f'  |  confident n={len(conf):4d} mean {sum(conf)/len(conf):5.2f} m '
                    f'max {max(conf):5.2f} m') if conf else '  |  no confident samples'
            print(f'{NAMES[idx]:16s} +{dt:.1f}s: n={len(errs):4d} '
                  f'mean {sum(errs)/len(errs):5.2f} m  max {max(errs):5.2f} m{ctxt}')
        for idx, name in NAMES.items():
            out = self.miss_outside[idx]
            nb = self.miss_no_blob[idx]
            far = self.miss_far[idx]
            if not (out or nb or far):
                continue
            line = (f'{name} izlenmeyen kareler: harita disinda {out}, '
                    f'harita icinde leke yok {nb}, leke var ama uzak {far}')
            if self.miss_far_d[idx]:
                line += (f' (ortalama {np.mean(self.miss_far_d[idx]):.1f} m)')
            if self.miss_edge_m[idx]:
                line += (f'; kacirilan kareler kenara ortalama '
                         f'{np.mean(self.miss_edge_m[idx]):.1f} m mesafede')
            print(line)
        for idx, name in NAMES.items():
            rows = self.speed_by_margin[idx]
            if not rows:
                continue
            near_edge = [v for m, v in rows if m < 4.0]
            inner = [v for m, v in rows if m >= 4.0]
            print(f'{name} hiz kestirimi kenara gore: '
                  f'<4 m {np.mean(near_edge):.2f} m/s ({len(near_edge)} kare), '
                  f'>=4 m {np.mean(inner):.2f} m/s ({len(inner)} kare)'
                  if near_edge and inner else
                  f'{name}: kenar ayrimi icin yeterli kare yok')
        raise SystemExit(0)


def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    rclpy.init()
    node = Scorer(duration)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
