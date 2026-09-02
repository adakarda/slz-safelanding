"""PX4 uXRCE-DDS topic names -- verified against the installed PX4 tree.

Only ``/fmu/out`` topics live here, and that is the point: **no node in this
project publishes to PX4**. Commanding the vehicle is the job of
``eland_mode``, which goes through the px4_ros2 library rather than hand-rolled
``/fmu/in`` traffic. The reference pipeline in ~/ws_slz did stream its own
OffboardControlMode heartbeats and VehicleCommand arming; if you find yourself
adding a ``/fmu/in/...`` constant back to this file, that is the design
regressing, not a missing constant.

Rule, from ``src/modules/uxrce_dds_client/utilities.hpp::generate_topic_name``:
a topic gets ``_v<MESSAGE_VERSION>`` appended iff its .msg declares a nonzero
``uint32 MESSAGE_VERSION``. Version 0 or absent -> bare name. Note the version
comes from **PX4's** msg definitions, not from the px4_msgs package -- pinning
px4_msgs does not move these names, only a PX4 upgrade does.

Measured on PX4 v1.17.0-alpha1 @ f63b0d6b6f, re-verified against px4_msgs
pinned at e62353e (branch ``px4-2026-05-01``):

    VehicleLocalPosition   MESSAGE_VERSION = 1  -> /fmu/out/vehicle_local_position_v1
    VehicleAttitude        MESSAGE_VERSION = 0  -> /fmu/out/vehicle_attitude

If a PX4 upgrade bumps a version, `ros2 topic list | grep fmu` shows the truth;
override the matching ``*_topic`` parameter in eland_params.yaml rather than
editing node source.
"""

VEHICLE_LOCAL_POSITION = '/fmu/out/vehicle_local_position_v1'

#: Not consumed yet. Phase 2 needs it for the real inverse perspective
#: mapping, which has to de-rotate the mask by the vehicle attitude instead of
#: assuming a perfectly nadir camera.
VEHICLE_ATTITUDE = '/fmu/out/vehicle_attitude'

__all__ = ['VEHICLE_LOCAL_POSITION', 'VEHICLE_ATTITUDE']
