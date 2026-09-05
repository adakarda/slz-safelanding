"""Semantic class convention -- single source of truth.

THE TAXONOMY IS THE SEGMENTATION MODEL'S

Indices 0..6 are exactly the seven SORA classes the thesis model is trained
on (TU Graz + MESSI, validated against Houston/Harvey), in the model's own
order. The simulator's ground truth and the model's output therefore live in
the same space and can be compared pixel for pixel without a translation
table -- which is the entire point of matching them.

    0 safe-soft   1 safe-hard   2 terrain-hazard   3 structure
    4 water       5 vehicle-animal                 6 person

UNKNOWN IS 7, AND SITS OUTSIDE THAT SEVEN

The model never emits it. The pipeline needs it: "this pixel was not
evaluated" is a different statement from any of the seven, and it must not be
landable. Gazebo returns label 0 for anything unlabelled, so if 0 meant
safe-soft here, then the sky, an unlabelled model and a labelling mistake
would all read as the safest ground in the world.

That is why the WORLD labels everything with `taxonomy index + 1`, and
perception_node subtracts one: Gazebo's 0 becomes UNKNOWN, and 1..7 become
0..6. The offset lives in exactly those two places -- the world generator that
writes the labels and the node that reads them.

RISK IS NOT THE MODEL'S CLASS WEIGHT

The thesis table also carries a weight per class: safe-soft 0.61, safe-hard
0.35, terrain-hazard 1.00, structure 0.44, water 2.33, vehicle-animal 1.81,
person 3.91. Those are inverse-frequency training weights, not risk, and the
arithmetic says so exactly:

    weight = 0.35 * sqrt(46.167 / pixel_percent)

reproduces all seven to two decimals. Using them as landing risk would rank
structure (0.44) as safer than safe-soft (0.61) -- a building preferred over
grass -- because a building is common in the dataset and grass is not. They
are kept here as TRAIN_WEIGHTS, for the training side that needs them, and
LANDING_RISK is a separate ordering that says what SORA says.
"""

SAFE_SOFT = 0
SAFE_HARD = 1
TERRAIN_HAZARD = 2
STRUCTURE = 3
WATER = 4
VEHICLE_ANIMAL = 5
PERSON = 6
#: Not one of the model's classes. See the module docstring.
UNKNOWN = 7

#: id -> human readable name
CLASS_NAMES = {
    SAFE_SOFT: 'safe-soft',
    SAFE_HARD: 'safe-hard',
    TERRAIN_HAZARD: 'terrain-hazard',
    STRUCTURE: 'structure',
    WATER: 'water',
    VEHICLE_ANIMAL: 'vehicle-animal',
    PERSON: 'person',
    UNKNOWN: 'unknown',
}

#: What the Gazebo world used to call things, and where each one now lands.
#: Kept as documentation of the merge rather than as a lookup: nothing reads
#: it at runtime, and the world writes the new indices directly.
#:
#: grass, dirt, sand      -> safe-soft
#: gravel, pavement       -> safe-hard
#: vegetation             -> terrain-hazard   (see below)
#: building, fence, pole  -> structure
#: water                  -> water
#: vehicle                -> vehicle-animal
#: person                 -> person
#:
#: Vegetation goes to terrain-hazard rather than safe-soft. Seen from above a
#: vegetation pixel is a canopy, and what is under a canopy is not observed at
#: all -- the aircraft would be committing to ground it has never seen. A
#: hedge and a lawn are both green from 25 m; only one of them can be landed
#: on, and the taxonomy has a class for exactly that distinction.
LEGACY_MERGE = {
    'grass': SAFE_SOFT, 'dirt': SAFE_SOFT, 'sand': SAFE_SOFT,
    'gravel': SAFE_HARD, 'pavement': SAFE_HARD,
    'vegetation': TERRAIN_HAZARD,
    'building': STRUCTURE, 'fence': STRUCTURE, 'pole': STRUCTURE,
    'water': WATER, 'vehicle': VEHICLE_ANIMAL, 'person': PERSON,
}

#: id -> risk, 0.0 safest .. 1.0 unlandable. Overridable via the `class_risk`
#: parameter on detector_node.
#:
#: safe-hard above safe-soft, not below it: the class weights have it the other
#: way round because tarmac is common in the dataset, which has nothing to do
#: with what a multicopter would rather touch down on.
DEFAULT_CLASS_RISK = {
    SAFE_SOFT: 0.0,
    SAFE_HARD: 0.2,
    TERRAIN_HAZARD: 0.7,
    STRUCTURE: 1.0,
    WATER: 1.0,
    VEHICLE_ANIMAL: 1.0,
    PERSON: 1.0,
    UNKNOWN: 1.0,
}

#: The thesis table's class weights, verbatim. Inverse-frequency balancing for
#: training the segmentation model -- NOT risk, see the module docstring.
#: Nothing in the landing pipeline reads these; they are here so the two sides
#: of the project keep one copy of the number.
TRAIN_WEIGHTS = {
    SAFE_SOFT: 0.61,
    SAFE_HARD: 0.35,
    TERRAIN_HAZARD: 1.00,
    STRUCTURE: 0.44,
    WATER: 2.33,
    VEHICLE_ANIMAL: 1.81,
    PERSON: 3.91,
}

#: The dataset pixel share each weight was derived from, also verbatim.
TRAIN_PIXEL_SHARE = {
    SAFE_SOFT: 15.5582,
    SAFE_HARD: 46.1670,
    TERRAIN_HAZARD: 5.7051,
    STRUCTURE: 29.4107,
    WATER: 1.0466,
    VEHICLE_ANIMAL: 1.7383,
    PERSON: 0.3741,
}

#: id -> RGB, for human-readable debug views only. Nothing decides anything
#: from these; they exist because the ground map's OccupancyGrid carries class
#: IDs rather than 0..100 occupancy, so RViz's map display renders it as
#: near-black nonsense. Chosen to be distinguishable rather than pretty, with
#: the two landable classes in green and grey and the two that rule a site out
#: on SORA grounds -- vehicle-animal and person -- in saturated warm colours.
CLASS_COLORS = {
    SAFE_SOFT: (86, 140, 61),
    SAFE_HARD: (148, 148, 140),
    TERRAIN_HAZARD: (43, 102, 36),
    STRUCTURE: (173, 166, 153),
    WATER: (36, 87, 143),
    VEHICLE_ANIMAL: (200, 40, 40),
    PERSON: (240, 150, 30),
    UNKNOWN: (40, 40, 40),
}

#: C_safe -- the only classes a landing may touch down on.
DEFAULT_SAFE_CLASSES = [SAFE_SOFT, SAFE_HARD]

#: Classes a landing site must keep an absolute SORA separation distance from.
#: Distinct from "not safe": UNKNOWN and TERRAIN_HAZARD are not landable, but
#: you do not owe them three metres of clearance -- you owe that to things that
#: can be hurt, and to structures you could strike. Everything not landable is
#: still handled by the smaller r_fit clearance.
DEFAULT_HAZARD_CLASSES = [STRUCTURE, WATER, VEHICLE_ANIMAL, PERSON]

#: Everything the pipeline can carry, including UNKNOWN. The model's own class
#: count is one less, and MODEL_CLASSES is the number to compare against it.
NUM_CLASSES = len(CLASS_NAMES)
MODEL_CLASSES = 7

#: Gazebo labels are written as `index + 1` so that nothing is labelled 0.
#: gen_world.py writes them, perception_node undoes them.
GZ_LABEL_OFFSET = 1

__all__ = [
    'SAFE_SOFT', 'SAFE_HARD', 'TERRAIN_HAZARD', 'STRUCTURE', 'WATER',
    'VEHICLE_ANIMAL', 'PERSON', 'UNKNOWN',
    'CLASS_NAMES', 'CLASS_COLORS', 'DEFAULT_CLASS_RISK', 'LEGACY_MERGE',
    'TRAIN_WEIGHTS', 'TRAIN_PIXEL_SHARE',
    'DEFAULT_SAFE_CLASSES', 'DEFAULT_HAZARD_CLASSES',
    'NUM_CLASSES', 'MODEL_CLASSES', 'GZ_LABEL_OFFSET',
]
