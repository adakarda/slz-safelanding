from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'eland_sim'


def model_data_files():
    """Install every model file under models/ preserving its directory layout.

    Gazebo resolves `model://seg_cam` by scanning GZ_SIM_RESOURCE_PATH for a
    directory containing model.config, so the tree shape has to survive the
    install step verbatim.

    Note that the running simulation does NOT read these installed copies:
    scripts/link_px4_assets.sh symlinks the *source* directories into the PX4
    tree, so editing an SDF takes effect without a rebuild. The install exists
    so the package is self-contained for anyone consuming it via
    GZ_SIM_RESOURCE_PATH instead of the symlinks.
    """
    entries = []
    for path in glob('models/**/*', recursive=True):
        if os.path.isfile(path):
            entries.append(
                (os.path.join('share', package_name, os.path.dirname(path)), [path]))
    return entries


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
    ] + model_data_files(),
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='arda',
    maintainer_email='adakarda34@gmail.com',
    description='Gazebo models, worlds, launch files and parameters for the '
                'emergency landing simulation.',
    license='MIT',
    entry_points={'console_scripts': []},
)
