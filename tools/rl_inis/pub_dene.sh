#!/bin/bash
# DO_REPOSITION mesajinin ros2 topic pub ile kurulup kurulamadigini dene (PX4 gerekmez; bos bir konuya yayinlar)
source /opt/ros/*/setup.bash
source ~/ros2_ws/install/setup.bash
timeout 20 ros2 topic pub -1 /deneme_vehicle_command px4_msgs/msg/VehicleCommand \
	"{command: 192, param1: -1.0, param2: 1.0, param4: .nan, param5: 47.64155783, param6: -122.14003167, param7: 150.5, target_system: 1, target_component: 1, source_system: 255, source_component: 190, from_external: true}" \
	--qos-reliability best_effort --qos-durability transient_local 2>&1 | tail -5
echo "cikis $?"
