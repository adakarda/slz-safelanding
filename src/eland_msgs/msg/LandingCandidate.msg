# A single candidate safe landing zone, expressed in the ENU map frame.
std_msgs/Header header
geometry_msgs/Point position    # meters, ENU, map frame
float32 radius                  # clearance to the nearest unsafe cell, meters
float32 risk_score              # 0.0 = safest, 1.0 = unsafe
float32 confidence              # 0.0 - 1.0
uint8 candidate_id
bool valid

# --- descent control inputs -------------------------------------------------
# These two drive the descent law in eland_mode. They are deliberately separate
# because they answer different questions, and collapsing them loses the
# distinction that makes the law work:
#
#   area_ratio  -- "how close am I?"    Measured in image space, so it needs no
#                                       altitude estimate and stays correct over
#                                       sloped or raised ground.
#   area_m2     -- "how big is it?"     Sets the ceiling on how fast the vehicle
#                                       is ever allowed to descend toward this
#                                       site. A small pad demands more care at
#                                       every altitude, not just near the end.
#
# Using area_ratio alone conflates the two: at 5 m a 10 m pad fills 95% of the
# view while a 4 m pad fills 15%, so a ratio-only law would dive fastest at
# exactly the site with the least room for error.
float32 area_ratio              # selected region area / camera field of view, 0..1
float32 area_m2                 # metric area of the selected connected safe region

# Whether area_ratio actually carries proximity information.
#
# A ratio approaching 1.0 is ambiguous: it means either "I am nearly on top of
# the site" or "the safe area is far bigger than my view". Nothing in the image
# distinguishes those without a scale reference -- except whether the region is
# fully enclosed by the frame. A region that runs off the edge tells you only a
# lower bound on its extent, so its ratio says nothing about how close you are.
#
# Measured: over open grassland the region touches the border at every
# altitude, area_ratio sat at 0.81+ from 20 m down, and a ratio-only descent
# law crawled the whole way at the 0.3 m/s floor -- 73 s instead of 27 s, with
# no slowdown near the ground because there was no slowdown left to make.
bool view_bounded
