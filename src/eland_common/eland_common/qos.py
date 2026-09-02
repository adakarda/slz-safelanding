"""Shared QoS profiles for the SLZ pipeline.

Defined once here and imported everywhere. Getting these wrong on ``/fmu/**``
fails *silently*: rclpy will happily publish and PX4 will simply never receive
anything, because the uXRCE-DDS client's data readers/writers only match
BEST_EFFORT + TRANSIENT_LOCAL + KEEP_LAST(1).

+-------------------------------------------------+----------------+
| Topic pattern                                   | Profile        |
+=================================================+================+
| ``/fmu/**``                                     | ``PX4_QOS``    |
| ``/camera/image``, ``/eland/semantic_mask``,      | ``SENSOR_QOS`` |
| ``/eland/ground_map``                             |                |
| ``/eland/candidate``, ``/eland/state``,             | ``DECISION_QOS``|
| ``/eland/target``                                 |                |
+-------------------------------------------------+----------------+
"""

from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)

#: PX4 uXRCE-DDS bridge. Must match exactly or messages are dropped silently.
PX4_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

#: High-rate image / grid data. Latest sample wins, drops are fine.
SENSOR_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

#: Decisions and state transitions. Must not be dropped.
DECISION_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)

__all__ = ['PX4_QOS', 'SENSOR_QOS', 'DECISION_QOS']
