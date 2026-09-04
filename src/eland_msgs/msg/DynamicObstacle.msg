# One tracked moving obstacle, in the ENU map frame.
#
# Everything here is INFERRED from the camera. Nothing in this message comes
# from the simulator's ground truth -- that lives on /eland/obstacle_truth and
# exists only to score these numbers afterwards.

uint32 id                       # stable while the track lives; reused after
uint8 class_id                  # eland_common class ID (8 vehicle, 9 person)

geometry_msgs/Point position    # meters, ENU, latest observed centroid
geometry_msgs/Vector3 velocity  # m/s, ENU, from a fit over the track history
float32 speed                   # |velocity|, published so consumers agree

# How much the velocity can be trusted, 0..1.
#
# Grown from the number of observations behind the fit and shrunk by the
# residual of that fit. A blob that appears once has no velocity worth having;
# a blob whose successive centroids do not lie on a line is either two objects
# being confused with each other or a segmentation edge flickering, and both
# deserve a wide corridor rather than a confident one.
float32 confidence

float32 age_s                   # how long this track has existed
uint32 observations             # centroids behind the current fit

# Straight-line extrapolation of `position` along `velocity`, one entry per
# prediction step, first entry earliest. Constant velocity on purpose: see
# tracker_node's header for why nothing cleverer is justified by what the
# segmentation actually delivers.
geometry_msgs/Point[] predicted

# Seconds ahead of `header.stamp` that `predicted[i]` refers to.
float32[] predicted_times
