#!/usr/bin/env python3
"""Inject a horizontal force disturbance on the airframe, and say what it is.

This is a *force* disturbance, not an aerodynamic wind model, and the thesis
should say so. Gazebo's WindEffects system needs `<enable_wind>` on every link
it acts on, and the airframe here merges PX4's own x500 model, which does not
set it -- patching PX4's model to get wind would put a local edit in the one
place this project deliberately does not fork. PX4's SITL server already loads
`gz-sim-apply-link-wrench-system`, so a wrench on the base link is available
for free and is under our control.

What it is equivalent to: for a small multirotor, drag is roughly
F = 0.5 rho Cd A v^2, which with Cd A ~ 0.1 m^2 gives about 0.06 v^2 newtons --
so 2 N is a ~6 m/s wind and 4 N a ~8 m/s one. Those are the numbers to quote,
with the approximation stated.

Profiles:
  step   constant force for the whole run -- steady-state droop and offset
  gust   `on_s` on, `off_s` off, repeating -- transient rejection
  ramp   linearly increasing to the target force -- the limit where it fails

Usage: wind_inject.py [--force N] [--dir DEG] [--profile step|gust|ramp]
                      [--duration S] [--on S] [--off S] [--world NAME]
                      [--model NAME] [--link NAME]
"""
import argparse
import subprocess
import sys
import time
import math

TOPIC = '/world/{world}/wrench/persistent'
CLEAR = '/world/{world}/wrench/clear'


def publish(topic, msg):
    """One `gz topic -p`. The CLI rather than the python bindings because the
    bindings are not installed with the Harmonic packages used here."""
    return subprocess.run(['gz', 'topic', '-t', topic, '-m',
                           'gz.msgs.EntityWrench', '-p', msg],
                          capture_output=True, text=True).returncode == 0


def wrench_msg(model, link, fx, fy):
    return (f'entity {{ name: "{model}::{link}", type: LINK }} '
            f'wrench {{ force {{ x: {fx:.3f} y: {fy:.3f} z: 0 }} '
            f'torque {{ x: 0 y: 0 z: 0 }} }}')


def clear(world, model, link):
    subprocess.run(['gz', 'topic', '-t', CLEAR.format(world=world), '-m',
                    'gz.msgs.Entity', '-p',
                    f'name: "{model}::{link}", type: LINK'],
                   capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--force', type=float, default=2.0, help='newtons')
    ap.add_argument('--dir', type=float, default=0.0,
                    help='degrees, 0 = +x (east)')
    ap.add_argument('--profile', choices=('step', 'gust', 'ramp'),
                    default='step')
    ap.add_argument('--duration', type=float, default=90.0)
    ap.add_argument('--on', type=float, default=4.0)
    ap.add_argument('--off', type=float, default=4.0)
    ap.add_argument('--world', default='eland_test')
    ap.add_argument('--model', default='x500_seg_cam_down')
    ap.add_argument('--link', default='base_link')
    a = ap.parse_args()

    topic = TOPIC.format(world=a.world)
    ang = math.radians(a.dir)
    t0 = time.time()
    last = None
    print(f'ruzgar: {a.profile}, {a.force:.1f} N ({a.force / 0.06:.0f} '
          f'm/s civari), yon {a.dir:.0f} derece, {a.duration:.0f} s')
    try:
        while time.time() - t0 < a.duration:
            t = time.time() - t0
            if a.profile == 'step':
                f = a.force
            elif a.profile == 'ramp':
                f = a.force * min(1.0, t / max(a.duration, 1e-3))
            else:
                f = a.force if (t % (a.on + a.off)) < a.on else 0.0
            if last is None or abs(f - last) > 1e-3:
                # Persistent wrenches accumulate: clear before replacing, or
                # the "gust off" phase would be the sum of everything sent so
                # far rather than zero.
                clear(a.world, a.model, a.link)
                if f > 0.0:
                    publish(topic, wrench_msg(a.model, a.link,
                                              f * math.cos(ang),
                                              f * math.sin(ang)))
                print(f'  t={t:5.1f} s  kuvvet {f:.2f} N')
                last = f
            time.sleep(0.2)
    finally:
        clear(a.world, a.model, a.link)
        print('ruzgar kaldirildi')
    return 0


if __name__ == '__main__':
    sys.exit(main())
