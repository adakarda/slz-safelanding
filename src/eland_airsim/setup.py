from glob import glob

from setuptools import find_packages, setup

package_name = 'eland_airsim'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.json')),
        ('share/' + package_name + '/data', glob('data/*')),
        ('share/' + package_name + '/scripts', glob('scripts/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='arda',
    maintainer_email='adakarda34@gmail.com',
    description='AirSim world for the emergency landing stack.',
    license='MIT',
    entry_points={'console_scripts': []},
)
