# Which height the descent law runs on, from eland_mode at ~10 Hz. Exists only
# with inis_yasasi_secimi: true; with it off the mode creates no publisher.
std_msgs/Header header

string secili                 # the inis_yasasi parameter now
string aktif                  # the law this descent uses
bool kilitli                  # COMMIT: aktif no longer follows secili
float32 harmanlama            # progress of a law change, 0..1 (1 = done)

float32 h_yasa_m              # the height the law used this tick
float32 h_ekf_m               # EKF height, for comparison

# Fallback: the source went stale (h_hat_bayat_s) or has nothing. The law then
# runs on h_ekf - yedek_fark_m, the offset at the last fresh sample, so the
# height does not step.
bool yedekte
string yedek_nedeni
float32 yedek_fark_m

# COMMIT entry, with the height that triggered it (NaN before COMMIT)
float32 commit_h_ekf_m
float32 commit_h_yasa_m
