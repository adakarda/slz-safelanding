"""Bring up the emergency landing perception pipeline against a running PX4
SITL + Gazebo session.

Deliberately does NOT launch PX4 SITL or MicroXRCEAgent -- those run in their
own terminals so their output stays visible.

    Terminal 1 -- PX4 SITL + Gazebo:
        cd ~/PX4-Autopilot/build/px4_sitl_default/rootfs
        HEADLESS=1 PX4_GZ_WORLD=eland_test PX4_SYS_AUTOSTART=4001 \
          PX4_SIM_MODEL=gz_x500_seg_cam_down GZ_IP=127.0.0.1 ../bin/px4

    Terminal 2:  MicroXRCEAgent udp4 -p 8888
    Terminal 3:  ros2 launch eland_sim eland_sim.launch.py

The world and model above are resolved out of the PX4 tree, not out of this
package: px4-rc.gzsim sources gz_env.sh, which unconditionally overwrites
PX4_GZ_WORLDS and PX4_GZ_MODELS, and spawns the model by literal path. Run
`scripts/link_px4_assets.sh` once (and again after a PX4 `make clean`) to
symlink this package's assets into place; that script explains the mechanics.

Nothing here works until the vehicle is off the ground. With the camera 0.28 m
up and a 99.7 deg field of view, a landed drone sees a 0.66 m patch consisting
almost entirely of its own unlabelled landing gear, so the mask reads 100%
UNKNOWN. That is correct behaviour, not a broken sensor.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration

# A pip-installed numpy 2.x in ~/.local shadows the apt numpy 1.26 that
# cv_bridge (and the rest of the apt ROS binaries) were compiled against, which
# makes `from cv_bridge import CvBridge` abort. Prepending the apt
# dist-packages to PYTHONPATH puts the matching numpy/cv2 first for these nodes
# only, without touching the user-level pip install. Drop `numpy_compat_env()`
# once the environments agree on a numpy major version.
APT_DIST_PACKAGES = '/usr/lib/python3/dist-packages'

# The seg_cam sensor sets <topic>seg_cam</topic> explicitly, so gz publishes on
# that name directly instead of deriving world/model/link/sensor. Semantic
# segmentation produces two topics off that stem; labels_map is the one the
# pipeline consumes, colored_map is for humans.
DEFAULT_GZ_LABELS_TOPIC = '/seg_cam/labels_map'
DEFAULT_GZ_COLORED_TOPIC = '/seg_cam/colored_map'


def numpy_compat_env() -> dict:
    """PYTHONPATH with the apt dist-packages prepended, or {} if already set."""
    current = os.environ.get('PYTHONPATH', '')
    if APT_DIST_PACKAGES in current.split(os.pathsep):
        return {}
    joined = os.pathsep.join(x for x in (APT_DIST_PACKAGES, current) if x)
    return {'PYTHONPATH': joined}


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory('eland_sim')
    default_params = os.path.join(pkg_share, 'config', 'eland_params.yaml')
    default_rviz = os.path.join(pkg_share, 'rviz', 'eland.rviz')

    args = [
        DeclareLaunchArgument(
            'params_file', default_value=default_params,
            description='Full path to the pipeline parameter YAML.'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='Start rviz2 alongside the pipeline.'),
        DeclareLaunchArgument(
            'rviz_config', default_value=default_rviz,
            description='RViz config file.'),
        DeclareLaunchArgument(
            'gz_labels_topic', default_value=DEFAULT_GZ_LABELS_TOPIC,
            description='gz-sim topic carrying the segmentation labels map.'),
        DeclareLaunchArgument(
            'gz_colored_topic', default_value=DEFAULT_GZ_COLORED_TOPIC,
            description='gz-sim topic carrying the colorised segmentation map.'),
        DeclareLaunchArgument(
            'bridge_colored', default_value='true',
            description='Also bridge colored_map to ROS for visual inspection. '
                        'Costs one extra image stream; turn off if the '
                        'simulation is struggling to keep up.'),
        DeclareLaunchArgument(
            'mode', default_value='true',
            description='Register the Emergency Landing flight mode with PX4. '
                        'Set false to run perception only, with no control '
                        'authority over the vehicle at all.'),
        DeclareLaunchArgument(
            'hud', default_value='true',
            description='Publish the landing HUD on /eland/hud. It costs one '
                        'rendered image at 5 Hz.'),
        DeclareLaunchArgument(
            'hud_view', default_value='false',
            description='Also open rqt_image_view on the HUD. Off by default '
                        'so that launching does not conjure a window in a '
                        'headless or remote session; run_sim.sh turns it on.'),
        DeclareLaunchArgument(
            'log_level', default_value='info',
            description='ROS log level for all pipeline nodes.'),
    ]

    params = LaunchConfiguration('params_file')
    log_level = LaunchConfiguration('log_level')
    labels_topic = LaunchConfiguration('gz_labels_topic')
    colored_topic = LaunchConfiguration('gz_colored_topic')
    log_args = ['--ros-args', '--log-level', log_level]

    # 1. gz -> ROS image bridges.
    labels_bridge = Node(
        package='ros_gz_image', executable='image_bridge',
        name='segmentation_labels_bridge',
        arguments=[labels_topic],
        remappings=[(labels_topic, '/camera/segmentation')],
        output='screen',
    )
    colored_bridge = Node(
        package='ros_gz_image', executable='image_bridge',
        name='segmentation_colored_bridge',
        arguments=[colored_topic],
        remappings=[(colored_topic, '/camera/segmentation_colored')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('bridge_colored')),
    )

    # 2. The perception chain. No control node here: from Phase 3 on, the
    #    landing behaviour is a registered PX4 mode (eland_mode), not a ROS
    #    node streaming offboard setpoints.
    compat_env = numpy_compat_env()
    pipeline_nodes = [
        Node(package=pkg, executable=exe, name=exe,
             parameters=[params], output='screen', arguments=log_args,
             additional_env=compat_env)
        for pkg, exe in (
            ('eland_perception', 'perception_node'),
            ('eland_mapping', 'mapping_node'),
            ('eland_mapping', 'detector_node'),
        )
    ]

    hud = Node(
        package='eland_viz', executable='hud_node', name='hud_node',
        parameters=[params], output='screen', arguments=log_args,
        additional_env=compat_env,
        condition=IfCondition(LaunchConfiguration('hud')),
    )
    # The viewer is a plain rqt_image_view pointed at the HUD topic. Keeping it
    # a separate process rather than rendering a window inside hud_node means
    # the HUD keeps publishing (and recording) when nobody is watching.
    hud_view = Node(
        package='rqt_image_view', executable='rqt_image_view',
        name='hud_view', arguments=['/eland/hud'], output='screen',
        condition=IfCondition(LaunchConfiguration('hud_view')),
    )

    # 3. The flight mode. Registers itself with PX4 on startup and then waits
    #    to be selected; starting it does not give it control of the vehicle.
    #    It is a separate executable rather than another entry in the list
    #    above because it is C++, and because the perception chain has to keep
    #    running unchanged when this is switched off.
    mode_node = Node(
        package='eland_mode', executable='emergency_landing_mode',
        name='emergency_landing_mode',
        parameters=[params], output='screen', arguments=log_args,
        condition=IfCondition(LaunchConfiguration('mode')),
    )

    # 4. Optional RViz, plus the static transform it needs to run at all.
    #
    #    Nothing in this pipeline publishes TF: the ground map carries its
    #    metric origin inside OccupancyGrid.info.origin, so the nodes never
    #    needed a transform tree. RViz does. With an empty tree its fixed frame
    #    "map" does not exist and every display fails, which looks like a
    #    broken pipeline when it is only a missing frame. This publisher exists
    #    purely to root the tree; the identity transform is meaningless beyond
    #    that, and if real TF is ever introduced this should be the first thing
    #    deleted.
    rviz_tf = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='map_root_tf',
        arguments=['--frame-id', 'map', '--child-frame-id', 'camera_link'],
        output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
    )
    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', LaunchConfiguration('rviz_config')],
        output='screen',
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return LaunchDescription(
        args + [labels_bridge, colored_bridge] + pipeline_nodes
        + [hud, hud_view, mode_node, rviz_tf, rviz])
