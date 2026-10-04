# Image-space coverage of the safe region under the image centre, one message
# per mask from detector_node when its publish_rho parameter is true. Same
# definitions as LandingCandidate.area_ratio / view_bounded, but at mask rate
# (~10 Hz) instead of decision rate (~1.8 Hz).
std_msgs/Header header   # stamp = the mask's capture stamp
float32 rho              # safe-region pixel share under the image centre, 0..1
bool view_bounded        # region does not touch the frame edge
