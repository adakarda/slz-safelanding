# Where the target surface is, estimated from the growth of the safe region.
# Published by p_kestirici, one message per /eland/rho message. Read-only
# information: nothing in the flight mode uses it.
#
# While the region fits in view, 1/sqrt(rho) = k * (h_ekf - P). A line fitted
# to the frames gives P where it crosses zero (the surface height in the EKF
# frame: about 0 on flat ground, about +4 on W5's platform) and the region's
# area from its slope, A = 4.216 / k^2. See eland_mapping/p_hesap.py.

std_msgs/Header header        # stamp = capture stamp of this frame's mask

uint8 VERI_YOK=0              # no usable frame since the descent started
uint8 TOPLANIYOR=1            # frames coming in, fit not trusted yet
uint8 GECERLI=2               # fit trusted, region still in view
uint8 DONMUS=3                # region no longer in view; last trusted fit held
uint8 durum

# This frame
float32 rho
bool view_bounded
bool kullanildi               # entered the fit (in view, tilt and rho limits)
float32 egiklik_deg           # body tilt from vertical
float32 h_ekf_m               # EKF height above take-off at the mask's capture
float32 v_asagi_mps           # EKF vertical speed, down positive

# The fit
uint16 kare_sayisi            # frames collected in this descent
uint16 kullanilan_kare        # frames the robust fit kept
float32 pencere_m             # h_ekf span of the collected frames
float32 p_m                   # surface height in the EKF frame; NaN without a fit
float32 p_sigma_m             # 1 sigma of p_m from the fit
float32 alan_m2               # region area from the slope; NaN without a fit
float32 artik_rms             # fit residual RMS, 1/sqrt(rho) units

# Derived
float32 h_hedef_m             # h_ekf - p_m: camera to surface; NaN without a fit
float32 alan_harita_m2        # LandingCandidate.area_m2 now, for comparison
float32 iraksama_1ps          # 0.5 d(ln rho)/dt over the last frames; NaN if not in view
float32 temas_suresi_s        # h_hedef / v_asagi; NaN without a fit or descent
