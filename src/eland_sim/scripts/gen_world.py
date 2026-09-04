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
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TEMPLATE = os.path.join(PKG, 'worlds', 'eland_test.sdf.in')
OUTPUT = os.path.join(PKG, 'worlds', 'eland_test.sdf')
PARAMS = os.path.join(PKG, 'config', 'eland_params.yaml')

MARKER = '@DYNAMIC_OBSTACLES@'

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


def person_model_block(p) -> str:
    """A cylinder labelled PERSON(9) at its start pose, driven at runtime.

    Same geometry as the static people already in the world, so a moving
    person and a standing one look identical to the perception chain -- which
    is the point: the only thing that should distinguish them downstream is
    that one of them moves.
    """
    start = p['person_start']
    return f"""    <model name="{p['person_name']}">
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
        <label>9</label>
      </plugin>
    </model>
"""


def person_actor_block(p) -> str:
    """A walking <actor> labelled PERSON(9), looping start -> goal -> start."""
    start, goal, speed = p['person_start'], p['person_goal'], p['person_speed']
    leg = _leg_time(start, goal, speed)
    out_h, back_h = _heading(start, goal), _heading(goal, start)
    # z: the actor mesh is authored with its origin at the feet, and Gazebo
    # places actors at the pose given -- 1.0 m sinks it to roughly waist
    # height on flat ground, which is what the PX4 example worlds use.
    z = p['person_z']
    return f"""    <actor name="{p['person_name']}">
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
        <label>9</label>
      </plugin>
    </actor>
"""


def vehicle_block(p) -> str:
    """A box labelled VEHICLE(8), parked at its start pose.

    Static on purpose. obstacle_driver teleports it along the trajectory
    rather than pushing it, so it needs no mass, no friction and no collision
    behaviour -- and cannot be knocked off course by the aircraft it is meant
    to be a hazard to. The collision geometry is kept only so the shape is
    visible to anything that queries the world geometrically.
    """
    start, goal = p['vehicle_start'], p['vehicle_goal']
    yaw = _heading(start, goal)
    size = p['vehicle_size']
    z = size[2] / 2.0
    return f"""    <model name="{p['vehicle_name']}">
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
        <label>8</label>
      </plugin>
    </model>
"""


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
    if kind == 'actor':
        person = person_actor_block(params)
    elif kind == 'model':
        person = person_model_block(params)
    else:
        raise SystemExit(f'person_kind must be "model" or "actor", got "{kind}"')
    return template.replace(MARKER, person + '\n' + vehicle_block(params))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--params', default=PARAMS)
    ap.add_argument('--output', default=OUTPUT)
    ap.add_argument('--check', action='store_true',
                    help='exit 1 if the output is stale, write nothing')
    args = ap.parse_args()

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
