from setuptools import find_packages, setup

package_name = 'eland_mapping'

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
    description='Ground mapping and safe landing zone detection.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'mapping_node = eland_mapping.mapping_node:main',
            'detector_node = eland_mapping.detector_node:main',
            'tracker_node = eland_mapping.tracker_node:main',
        ],
    },
)
