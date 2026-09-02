cmake_minimum_required(VERSION 3.8)
project(eland_mode)

if(NOT CMAKE_CXX_STANDARD)
    set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(eigen3_cmake_module REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(px4_ros2_cpp REQUIRED)
find_package(eland_msgs REQUIRED)

include_directories(include ${Eigen3_INCLUDE_DIRS})

add_executable(emergency_landing_mode src/main.cpp)
target_link_libraries(emergency_landing_mode
    PUBLIC Eigen3::Eigen px4_ros2_cpp::px4_ros2_cpp rclcpp::rclcpp
           ${eland_msgs_TARGETS})

install(TARGETS emergency_landing_mode DESTINATION lib/${PROJECT_NAME})

ament_package()
