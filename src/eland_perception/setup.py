from setuptools import find_packages, setup

package_name = 'eland_perception'

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
    description='Semantic segmentation front-end for the emergency landing pipeline.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'perception_node = eland_perception.perception_node:main',
        ],
    },
)
