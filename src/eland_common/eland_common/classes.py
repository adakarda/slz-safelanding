"""Semantic class ID convention -- single source of truth.

The semantic mask is ``mono8``; each pixel value *is* the class ID below.
``eland_perception`` emits these IDs and nothing else -- no risk values.
Risk lookup and the definition of "landable" live in ``detector_node``.
"""

UNKNOWN = 0
GRASS = 1
DIRT = 2
GRAVEL = 3
PAVEMENT = 4
VEGETATION = 5
BUILDING = 6
WATER = 7
VEHICLE = 8
PERSON = 9

#: id -> human readable name
CLASS_NAMES = {
    UNKNOWN: 'unknown',
    GRASS: 'grass',
    DIRT: 'dirt',
    GRAVEL: 'gravel',
    PAVEMENT: 'pavement',
    VEGETATION: 'vegetation',
    BUILDING: 'building',
    WATER: 'water',
    VEHICLE: 'vehicle',
    PERSON: 'person',
}

#: id -> default risk, 0.0 safest .. 1.0 unsafe. Overridable via the
#: ``class_risk`` parameter on ``detector_node``.
DEFAULT_CLASS_RISK = {
    UNKNOWN: 1.0,
    GRASS: 0.0,
    DIRT: 0.1,
    GRAVEL: 0.2,
    PAVEMENT: 0.4,
    VEGETATION: 0.7,
    BUILDING: 1.0,
    WATER: 1.0,
    VEHICLE: 1.0,
    PERSON: 1.0,
}

#: id -> RGB, for human-readable debug views only. Nothing decides anything
#: from these; they exist because the ground map's OccupancyGrid carries class
#: IDs rather than 0..100 occupancy, so RViz's map display renders it as
#: near-black nonsense. Chosen to be distinguishable rather than pretty, with
#: the three landable classes in greens/browns and the two that rule a site
#: out on SORA grounds -- vehicle and person -- in saturated warm colours.
CLASS_COLORS = {
    UNKNOWN: (40, 40, 40),
    GRASS: (86, 140, 61),
    DIRT: (133, 97, 59),
    GRAVEL: (148, 148, 140),
    PAVEMENT: (61, 61, 64),
    VEGETATION: (43, 102, 36),
    BUILDING: (173, 166, 153),
    WATER: (36, 87, 143),
    VEHICLE: (200, 40, 40),
    PERSON: (240, 150, 30),
}

#: C_safe -- the only classes a landing may touch down on.
DEFAULT_SAFE_CLASSES = [GRASS, DIRT, GRAVEL]

#: Classes a landing site must keep an absolute SORA separation distance from.
#: Distinct from "not safe": UNKNOWN and VEGETATION are not landable, but you
#: do not owe them three metres of clearance -- you owe that to things that can
#: be hurt, and to structures you could strike. Everything not landable is
#: still handled by the smaller r_fit clearance.
DEFAULT_HAZARD_CLASSES = [BUILDING, WATER, VEHICLE, PERSON]

NUM_CLASSES = len(CLASS_NAMES)

__all__ = [
    'UNKNOWN', 'GRASS', 'DIRT', 'GRAVEL', 'PAVEMENT', 'VEGETATION',
    'BUILDING', 'WATER', 'VEHICLE', 'PERSON',
    'CLASS_NAMES', 'CLASS_COLORS', 'DEFAULT_CLASS_RISK',
    'DEFAULT_SAFE_CLASSES', 'DEFAULT_HAZARD_CLASSES', 'NUM_CLASSES',
]
