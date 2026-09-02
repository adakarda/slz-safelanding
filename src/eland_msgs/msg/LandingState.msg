# Landing manager state machine output. Primary debug channel.
std_msgs/Header header

uint8 SEARCH=0
uint8 APPROACH=1
uint8 VALIDATE=2
uint8 HOLD=3
uint8 ABORT=4
uint8 COMMIT=5

uint8 state
string reason
float32 altitude_agl

# --- what the descent law decided this tick ---------------------------------
# Published rather than left to be parsed out of `reason`, so the HUD and any
# log analysis read the same numbers the controller actually used.
float32 commanded_descent_mps   # the vertical speed limit handed to PX4
float32 descent_ceiling_mps     # clamp(k * sqrt(area), v_min, v_max)
float32 area_ratio              # the control variable, 0..1
bool area_law_active            # false while falling back to the altitude law
