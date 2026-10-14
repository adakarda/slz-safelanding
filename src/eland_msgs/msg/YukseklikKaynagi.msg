# Every height the descent law can be switched to (eland_mode inis_yasasi),
# in one message from yukseklik_gozlemci at ~50 Hz.
#
# Heights are in the mode's own convention: 0 with the aircraft at rest on the
# surface below it (the camera estimates minus kamera_ofseti_m). NaN means
# that source has nothing now: not initialised for this descent, not running,
# or not a simulation.
std_msgs/Header header        # stamp = simulation time of the estimate
float32 rtf                   # real-time factor: simulation s per wall s, over ~2 s
bool damga_kullaniliyor       # frames compared at their capture stamp (false: clocks disagree)

float32 h_ekf_m               # -z of vehicle_local_position: take-off referenced, today's law
float32 h_gozlemci_m          # the observer, gozlemci_tipi below
float32 h_dogrudan_m          # sqrt(A0 / (4.216 rho)), A0 = area_m2 frozen at VALIDATE entry
float32 h_kahin_m             # Gazebo truth above the surface below (simulation only, reference)
float32 h_lazer_m             # EKF dist_bottom, only with dist_bottom_valid (no rangefinder: NaN)

string gozlemci_tipi          # "sabit" | "kalman"
bool gecerli                  # h_gozlemci initialised for this descent

# observer internals (gozlem_hesap.py)
float32 x_hat                 # ln of the camera height estimate
float32 c_hat                 # ln(A / 4.216)
float32 alan_m2               # 4.216 * exp(c_hat)
float32 nu                    # innovation of the last frame (0 when gated before it)
float32 sigma_h_m             # Kalman 1-sigma of h_gozlemci (NaN for sabit)
float32 iraksama_1ps          # D = vz / h, h from the observer
float32 iraksama_kahin_1ps    # D = vz / h, h from the truth (simulation only)
float32 v_asagi_mps           # EKF vertical speed, down +

# Gates, as gozlem_hesap.KAPI_*: the last frame's bits, and counts this descent
uint8 KAPI_RHO_YOK=1
uint8 KAPI_DOYUM=2
uint8 KAPI_SINIR=4
uint8 KAPI_EGIKLIK=8
uint8 KAPI_AYKIRI=16
uint8 son_kapi
uint32 kullanilan_kare
uint32 kapi_rho_yok
uint32 kapi_doyum
uint32 kapi_sinir
uint32 kapi_egiklik
uint32 kapi_aykiri

# Locked: at least kilit_kare outlier frames in a row. The gate keeps rejecting,
# the estimate keeps propagating; this only makes it visible.
bool kilitli
float32 kilit_suresi_s        # how long it has been locked, 0 when not
