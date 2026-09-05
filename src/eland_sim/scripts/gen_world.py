#!/usr/bin/env python3
"""Render worlds/eland_test.sdf from eland_test.sdf.in plus the obstacle
parameters in config/eland_params.yaml.

WHY THE WORLD IS GENERATED

The dynamic person is a Gazebo <actor>, and an actor's motion is a waypoint
script inside its own SDF: Gazebo owns the pose, and nothing outside can move
it. So "start, goal and speed are parameters, not hardcoded numbers" can only
be honoured for the person by writing the SDF from those parameters. The
vehicle does not need this -- it is a plain model driven at runtime by
obstacle_driver -- but it is emitted here too so that both obstacles come from
one set of numbers and one file.

PERSON: MODEL BY DEFAULT, ACTOR AVAILABLE

`person_kind` picks the mechanism. It defaults to `model` -- a labelled
cylinder teleported by obstacle_driver, exactly like the vehicle -- and that
is a retreat from the nicer-looking option, made for a specific measured
reason.

The <actor> works as far as segmentation is concerned: it is labelled, it
walks, and the tracker sees it. What it does not do is walk at the speed it
was asked to. Its own script says 20 m at 1.2 m/s, so 16.7 s per leg and a
33.3 s round trip; traced against the tracker it completed a round trip in
about 28 s, roughly 17% fast, and Gazebo publishes no pose for an actor
(neither pose/info nor dynamic_pose/info lists one) so there is nothing to
correct against. An obstacle whose true position is neither commanded nor
observable cannot score a position estimator: every error becomes ambiguous
between the estimator and the reference.

Set `person_kind: actor` to get the walking mesh back -- useful for anything
visual, and for reproducing the finding above. The class label, the
trajectory parameters and everything downstream are identical either way.

WHY THE VEHICLE IS NOT AN ACTOR

Measured on this machine (gz-sim 8.11.0), both mechanisms work and each is the
only one available to its entity type:

  - An <actor> carrying a Label plugin IS picked up by the segmentation
    camera. Probed with an actor labelled 3 against static controls: label 3
    appeared at 123 px and its centroid moved 124.8 -> 207.0 px over 5 s while
    the static controls did not move. Actors also give a real walking human
    rather than a sliding cylinder.
  - A labelled model CAN be moved by the world's set_pose service, static or
    not, and the segmentation camera follows it: the control vehicle's
    centroid moved (100.7, 119.5) -> (101.8, 212.6) px on one call.

An actor cannot be driven externally (its script owns its pose) and a model
cannot run a waypoint script, so the split is not a preference.

ACTOR TIMING

Waypoint times are distances divided by the requested speed, so the actor
walks at that speed. The <script> loops start -> goal -> start, which keeps
the obstacle in the scene indefinitely; a one-way walk would leave the map
after one pass and quietly turn every later test into a static-world test.

interpolate_x is false. With it on, Gazebo drives the actor's forward position
from the walk animation's own root motion so the feet do not slide, which
looks better and means the actor is no longer where its waypoint script says
it is. Since the script is the only ground truth available for the person --
Gazebo publishes no actor pose -- that trade is the wrong way round here:
sliding feet cost nothing, an unmeasurable position costs the measurement.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys

import yaml

# Same directory: the spawn picker already knows how to read standing
# obstacles out of a world, and mobs have to avoid the same things the
# aircraft does.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pick_spawn import (_point_segment_distance,  # noqa: E402
                        obstacles_from_world)

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TEMPLATE = os.path.join(PKG, 'worlds', 'eland_test.sdf.in')
OUTPUT = os.path.join(PKG, 'worlds', 'eland_test.sdf')
# Where the drawn mob routes are written. The world and obstacle_driver both
# read this file rather than each re-deriving the layout from a seed: one draw,
# one record, and no way for the models and the motion to disagree.
LAYOUT = os.path.join(PKG, 'worlds', 'mob_layout.yaml')
PARAMS = os.path.join(PKG, 'config', 'eland_params.yaml')

MARKER = '@DYNAMIC_OBSTACLES@'

#: Where the aircraft will start, when the caller knows. Set from --focus.
FOCUS = None

# Fuel is only reached the first time: gz caches the mesh under ~/.gz/fuel and
# every later run is offline. Recorded here because a first run on a machine
# with no network gets an actor that renders nothing -- and an actor that
# renders nothing is invisible to segmentation, which looks like a labelling
# bug rather than a missing download.
ACTOR_SKIN = ('https://fuel.gazebosim.org/1.0/Mingfei/models/actor/tip/'
              'files/meshes/walk.dae')


def _leg_time(start, goal, speed):
    dist = math.hypot(goal[0] - start[0], goal[1] - start[1])
    if speed <= 0.0:
        raise ValueError(f'speed must be positive, got {speed}')
    return dist / speed


def _heading(start, goal):
    return math.atan2(goal[1] - start[1], goal[0] - start[0])


def leg_for(index, start, goal, spacing):
    """Start and goal for obstacle `index`, offset sideways from the base leg.

    Several obstacles of the same kind share one pair of numbers in the
    parameter file and are spread out from it: obstacle 0 runs the leg as
    written, and each one after it is pushed `spacing` metres to the side,
    alternating so the group stays centred on the original route rather than
    drifting off it. The phase offset that keeps them from moving in lockstep
    is applied at runtime by obstacle_driver, not here -- this file only has
    to place them.
    """
    if index == 0:
        return list(start), list(goal)
    # 1, -1, 2, -2, ... so the group grows either side of the original line.
    step = ((index + 1) // 2) * (1 if index % 2 else -1)
    heading = _heading(start, goal)
    nx, ny = -math.sin(heading), math.cos(heading)
    off = step * spacing
    return ([start[0] + nx * off, start[1] + ny * off],
            [goal[0] + nx * off, goal[1] + ny * off])


def _closest_point(point, seg):
    """Where along `seg` it passes closest to `point`."""
    ax, ay, bx, by = seg
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return ax, ay
    t = max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / denom))
    return ax + t * dx, ay + t * dy


def _segment_clearance(seg, obstacles):
    """Smallest gap between a route and any standing obstacle."""
    if not obstacles:
        return float('inf')
    best = float('inf')
    for ox, oy, px, py, r, _n in obstacles:
        # Both ways round: the shortest distance between two segments is not
        # found by measuring one segment's endpoints against the other.
        best = min(best, _segment_gap(seg, (ox, oy, px, py)) - r)
    return best


def _segment_gap(a, b, samples=12):
    """Rough distance between two routes.

    Sampled points from each segment against the other, and both directions
    are needed: sampling only one way is asymmetric, and a pair that passed
    the check measured the other way round came out at 5.90 m against a 6.00 m
    threshold. Exact segment-to-segment distance is not worth the algebra for
    a threshold that is a judgement call anyway, but the check should at least
    give the same answer whichever route was drawn first.
    """
    best = float('inf')
    for first, second in ((a, b), (b, a)):
        for i in range(samples + 1):
            t = i / samples
            px = first[0] + (first[2] - first[0]) * t
            py = first[1] + (first[3] - first[1]) * t
            best = min(best, _point_segment_distance(px, py, *second))
    return best


def draw_mobs(params, obstacles, rng, focus=None):
    """Pick routes for the moving obstacles: how many, from where to where.

    Capped rather than open-ended. Every extra mob is another blob for the
    tracker to confuse with its neighbours and another set of discs for the
    corridor test to rasterise, and the point of the cap is that a scenario
    should get more varied without getting slower.

    `focus` is where the aircraft will start. Routes are drawn through a disc
    around it rather than anywhere in the world, because traffic the aircraft
    never sees is not a scenario -- measured on the first version, which
    scattered five mobs across sixty metres and left the tracker with nothing
    to track for the whole flight. They still keep their distance from the
    spawn itself, so the run does not begin with a vehicle on top of the
    aircraft.
    """
    n_max = max(0, int(params.get('max_mobs', 6)))
    want_people = max(0, int(params.get('person_count', 3)))
    want_vehicles = max(0, int(params.get('vehicle_count', 2)))
    total = want_people + want_vehicles
    if total > n_max and total > 0:
        # Trim proportionally, keeping at least one of each that was asked for.
        keep_p = max(1 if want_people else 0, round(n_max * want_people / total))
        keep_v = max(1 if want_vehicles else 0, n_max - keep_p)
        want_people, want_vehicles = keep_p, keep_v

    bounds = [float(v) for v in params.get('mob_bounds', [-30.0, -30.0, 30.0, 30.0])]
    clearance = float(params.get('mob_clearance_m', 2.5))
    route_gap = float(params.get('mob_route_gap_m', 6.0))
    length_range = params.get('mob_route_length_m', [16.0, 70.0])
    focus_r = float(params.get('mob_focus_radius_m', 18.0))
    spawn_gap = float(params.get('mob_spawn_gap_m', 8.0))

    layout = []
    routes = []
    crossings = []
    for kind, count, speed, z in (
            ('vehicle', want_vehicles, float(params['vehicle_speed']),
             float(params['vehicle_size'][2]) / 2.0),
            ('person', want_people, float(params['person_speed']), 0.9)):
        for i in range(count):
            seg = None
            for _try in range(500):
                heading = rng.uniform(-math.pi, math.pi)
                length = rng.uniform(float(length_range[0]), float(length_range[1]))
                # Drawn anywhere, then kept only if it happens to pass the
                # aircraft at a sensible distance. Constructing the route
                # around a point near the aircraft is the obvious alternative
                # and it is worse: forcing the crossing to be the midpoint
                # pins both ends too, and near the middle of this world --
                # trees at (-12, 5) and (9, -13), fences along y = -15 -- most
                # of those routes run into something. Measured: 2.15 mobs
                # placed on average against a requested five.
                x0 = rng.uniform(bounds[0], bounds[2])
                y0 = rng.uniform(bounds[1], bounds[3])
                cand = (x0, y0,
                        x0 + math.cos(heading) * length,
                        y0 + math.sin(heading) * length)
                if _segment_clearance(cand, obstacles) < clearance:
                    continue
                if focus is not None:
                    passes = _point_segment_distance(focus[0], focus[1], *cand)
                    # Close enough that the aircraft will see it, far enough
                    # that the run does not begin inside its exclusion zone.
                    if passes > focus_r or passes < spawn_gap:
                        continue
                    px = focus[0]
                    py = focus[1]
                # Routes may cross -- traffic does -- but must not run down
                # the same line. Requiring a gap everywhere along their length
                # made the second mob impossible to place once every route had
                # to thread the same disc; requiring it only where they pass
                # the aircraft is the constraint that actually matters.
                if focus is not None:
                    near = [_closest_point(focus, cand)]
                    if any(math.hypot(near[0][0] - qx, near[0][1] - qy) < route_gap
                           for qx, qy in crossings):
                        continue
                elif any(_segment_gap(cand, other) < route_gap for other in routes):
                    continue
                seg = cand
                break
            if seg is None:
                # This one did not fit. Try the next rather than abandoning the
                # rest of its kind: an early failure used to leave a run with a
                # single vehicle and no people at all, which is not "fewer
                # mobs", it is a different scenario.
                continue
            routes.append(seg)
            if focus is not None:
                crossings.append(_closest_point(focus, seg))
            name = f"{params['vehicle_name'] if kind == 'vehicle' else params['person_name']}_{len([m for m in layout if m['kind'] == kind])}"
            layout.append({
                'kind': kind,
                'name': name,
                'start': [round(seg[0], 2), round(seg[1], 2)],
                'goal': [round(seg[2], 2), round(seg[3], 2)],
                'speed': speed,
                'z': z,
            })
    return layout


def person_model_block(p, name=None, start=None) -> str:
    """A cylinder labelled PERSON(9) at its start pose, driven at runtime.

    Same geometry as the static people already in the world, so a moving
    person and a standing one look identical to the perception chain -- which
    is the point: the only thing that should distinguish them downstream is
    that one of them moves.
    """
    start = start if start is not None else p['person_start']
    name = name or p['person_name']
    return f"""    <model name="{name}">
      <static>true</static>
      <pose>{start[0]} {start[1]} 0.9 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <geometry><cylinder><radius>0.3</radius><length>1.8</length></cylinder></geometry>
        </collision>
        <visual name="visual">
          <geometry><cylinder><radius>0.3</radius><length>1.8</length></cylinder></geometry>
          <material>
            <ambient>0.70 0.45 0.10 1</ambient>
            <diffuse>0.90 0.58 0.13 1</diffuse>
          </material>
        </visual>
      </link>
      <plugin filename="gz-sim-label-system" name="gz::sim::systems::Label">
        <label>7</label>
      </plugin>
    </model>
"""


def person_actor_block(p, name=None, start=None, goal=None) -> str:
    """A walking <actor> labelled PERSON(9), looping start -> goal -> start."""
    start = start if start is not None else p['person_start']
    goal = goal if goal is not None else p['person_goal']
    speed = p['person_speed']
    name = name or p['person_name']
    leg = _leg_time(start, goal, speed)
    out_h, back_h = _heading(start, goal), _heading(goal, start)
    # z: the actor mesh is authored with its origin at the feet, and Gazebo
    # places actors at the pose given -- 1.0 m sinks it to roughly waist
    # height on flat ground, which is what the PX4 example worlds use.
    z = p['person_z']
    return f"""    <actor name="{name}">
      <skin>
        <filename>{ACTOR_SKIN}</filename>
        <scale>1.0</scale>
      </skin>
      <animation name="walk">
        <filename>{ACTOR_SKIN}</filename>
        <interpolate_x>false</interpolate_x>
      </animation>
      <script>
        <loop>true</loop>
        <delay_start>0.0</delay_start>
        <auto_start>true</auto_start>
        <trajectory id="0" type="walk">
          <waypoint>
            <time>0</time>
            <pose>{start[0]} {start[1]} {z} 0 0 {out_h:.4f}</pose>
          </waypoint>
          <waypoint>
            <time>{leg:.2f}</time>
            <pose>{goal[0]} {goal[1]} {z} 0 0 {out_h:.4f}</pose>
          </waypoint>
          <waypoint>
            <time>{2 * leg:.2f}</time>
            <pose>{start[0]} {start[1]} {z} 0 0 {back_h:.4f}</pose>
          </waypoint>
        </trajectory>
      </script>
      <plugin filename="gz-sim-label-system" name="gz::sim::systems::Label">
        <label>7</label>
      </plugin>
    </actor>
"""


def vehicle_block(p, name=None, start=None, goal=None) -> str:
    """A box labelled VEHICLE(8), parked at its start pose.

    Static on purpose. obstacle_driver teleports it along the trajectory
    rather than pushing it, so it needs no mass, no friction and no collision
    behaviour -- and cannot be knocked off course by the aircraft it is meant
    to be a hazard to. The collision geometry is kept only so the shape is
    visible to anything that queries the world geometrically.
    """
    start = start if start is not None else p['vehicle_start']
    goal = goal if goal is not None else p['vehicle_goal']
    name = name or p['vehicle_name']
    yaw = _heading(start, goal)
    size = p['vehicle_size']
    z = size[2] / 2.0
    return f"""    <model name="{name}">
      <static>true</static>
      <pose>{start[0]} {start[1]} {z} 0 0 {yaw:.4f}</pose>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>{size[0]} {size[1]} {size[2]}</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>{size[0]} {size[1]} {size[2]}</size></box></geometry>
          <material>
            <ambient>0.10 0.20 0.45 1</ambient>
            <diffuse>0.14 0.28 0.62 1</diffuse>
          </material>
        </visual>
      </link>
      <plugin filename="gz-sim-label-system" name="gz::sim::systems::Label">
        <label>6</label>
      </plugin>
    </model>
"""


def write_layout(doc):
    """Record the drawn layout where obstacle_driver will look for it.

    Written twice when the workspace is installed: the source tree, which is
    what Gazebo reads through the symlinks, and the installed share directory,
    which is where an installed node looks. Without the second copy a fresh
    draw would move the models while the driver kept teleporting them to the
    positions from the last colcon build -- the exact silent disagreement this
    file exists to prevent.
    """
    targets = [LAYOUT]
    installed = os.path.join(os.path.expanduser('~'), 'ros2_ws', 'install',
                             'eland_sim', 'share', 'eland_sim', 'worlds')
    if os.path.isdir(installed):
        targets.append(os.path.join(installed, 'mob_layout.yaml'))
    for target in targets:
        with open(target, 'w', encoding='utf-8') as handle:
            yaml.safe_dump(doc, handle, default_flow_style=False,
                           sort_keys=False)


def load_params(path=PARAMS):
    with open(path, 'r', encoding='utf-8') as handle:
        doc = yaml.safe_load(handle)
    try:
        return doc['obstacle_driver']['ros__parameters']
    except (KeyError, TypeError) as exc:
        raise SystemExit(
            f'{path} has no obstacle_driver/ros__parameters section') from exc


def render(params) -> str:
    with open(TEMPLATE, 'r', encoding='utf-8') as handle:
        template = handle.read()
    # Exactly once, checked rather than assumed: the first version of this
    # template also named the marker in its header comment, and plain text
    # replacement duly emitted a second copy of both obstacles inside that
    # comment, where they were invisible to Gazebo and to the reader.
    occurrences = template.count(MARKER)
    if occurrences != 1:
        raise SystemExit(
            f'{TEMPLATE} contains {MARKER} {occurrences} times, expected once')
    if not params.get('enable', True):
        # An empty block rather than a skipped generator run: the world on
        # disk should always match the parameters, including "no obstacles".
        return template.replace(MARKER, '    <!-- dynamic obstacles disabled -->')
    kind = params.get('person_kind', 'model')
    if kind not in ('actor', 'model'):
        raise SystemExit(f'person_kind must be "model" or "actor", got "{kind}"')

    blocks = []

    if params.get('randomize_mobs', True):
        # Routes drawn fresh, then written down. Both the models below and
        # obstacle_driver read that record, so there is exactly one draw and
        # no seed for two programs to re-derive identically.
        seed = params.get('mob_seed')
        seed = random.randrange(1 << 30) if seed in (None, 0) else int(seed)
        rng = random.Random(seed)
        obstacles = obstacles_from_world(TEMPLATE, 0.5)
        layout = draw_mobs(params, obstacles, rng, focus=FOCUS)
        print(f'{len(layout)} mob drawn (seed {seed})')
    else:
        # The fixed layout: obstacle 0 on the configured leg, the rest offset
        # sideways from it. Kept for comparison runs, where two halves of an
        # experiment have to face the same traffic.
        #
        # Vehicles first, then people -- the same order the random branch uses
        # and the order the truth topic's contract states. This branch had it
        # the other way round, which put a person at index 0 and made every
        # vehicle measurement compare an estimate against the wrong obstacle:
        # reported as "vehicle never tracked" when the vehicle was tracked
        # perfectly well.
        layout = []
        for i in range(max(0, int(params.get('vehicle_count', 1)))):
            start, goal = leg_for(i, params['vehicle_start'], params['vehicle_goal'],
                                  float(params.get('vehicle_spacing_m', 7.0)))
            layout.append({'kind': 'vehicle', 'name': f"{params['vehicle_name']}_{i}",
                           'start': list(start), 'goal': list(goal),
                           'speed': float(params['vehicle_speed']),
                           'z': float(params['vehicle_size'][2]) / 2.0})
        for i in range(max(0, int(params.get('person_count', 1)))):
            start, goal = leg_for(i, params['person_start'], params['person_goal'],
                                  float(params.get('person_spacing_m', 6.0)))
            layout.append({'kind': 'person', 'name': f"{params['person_name']}_{i}",
                           'start': list(start), 'goal': list(goal),
                           'speed': float(params['person_speed']), 'z': 0.9})
        seed = None

    write_layout({'seed': seed, 'mobs': layout})

    for mob in layout:
        if mob['kind'] == 'person':
            blocks.append(person_actor_block(params, mob['name'], mob['start'],
                                             mob['goal'])
                          if kind == 'actor'
                          else person_model_block(params, mob['name'], mob['start']))
        else:
            blocks.append(vehicle_block(params, mob['name'], mob['start'],
                                        mob['goal']))

    return template.replace(MARKER, chr(10).join(blocks))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--params', default=PARAMS)
    ap.add_argument('--output', default=OUTPUT)
    ap.add_argument('--focus', default=None,
                    help='x,y the mob routes should pass near -- normally the '
                         'spawn pose, so the traffic is where the aircraft is')
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if the output is stale, write nothing')
    args = ap.parse_args()

    global FOCUS
    if args.focus:
        parts = [float(v) for v in args.focus.split(',')[:2]]
        FOCUS = (parts[0], parts[1])
    text = render(load_params(args.params))

    if args.check:
        current = ''
        if os.path.exists(args.output):
            with open(args.output, 'r', encoding='utf-8') as handle:
                current = handle.read()
        if current != text:
            print(f'{args.output} is stale', file=sys.stderr)
            return 1
        return 0

    with open(args.output, 'w', encoding='utf-8') as handle:
        handle.write(text)
    print(f'wrote {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
