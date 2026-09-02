from setuptools import find_packages, setup

package_name = 'eland_viz'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='arda',
    maintainer_email='adakarda34@gmail.com',
    description='Landing HUD: what the pipeline sees, what it chose, and why.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'hud_node = eland_viz.hud_node:main',
            'control_station = eland_viz.control_station:main',
        ],
    },
)
