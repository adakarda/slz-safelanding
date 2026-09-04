# Every obstacle tracker_node currently believes in.
#
# Published on every frame, empty array included: "I see nothing moving" is a
# result the landing logic needs to receive, not the absence of one. A
# consumer that only ever hears about obstacles cannot tell a quiet scene from
# a dead tracker, and the difference decides whether it is safe to descend.

std_msgs/Header header
eland_msgs/DynamicObstacle[] obstacles

# Prediction horizon these obstacles were extrapolated over, seconds.
float32 horizon_s
