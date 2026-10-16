from setuptools import find_packages, setup

package_name = 'eland_rl'

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
    description='Light training environment and policy for the RL emergency '
                'landing study.',
    license='MIT',
    entry_points={'console_scripts': []},
)
