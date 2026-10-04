"""Success levels by touchdown speed (Tur 4, madde 4).

`basarili` keeps its meaning: PX4 landed, not blind, touchdown point on the
target surface (open field: the last mask before touchdown has a landable
class at its centre). On top of it, two levels by the true touchdown speed
`temas_dikey_hiz_gercek_hesap_mps` (highest descent rate in the 0.3 s before
ground-truth contact, from Gazebo):

    basarili_v05   basarili and touchdown speed < 0.5 m/s
    basarili_v10   basarili and touchdown speed < 1.0 m/s

An episode without a touchdown speed meets neither level. A hard touchdown
in the reports is a speed at or above the level, the complement of "<".
"""
import math

# (field, threshold m/s), the two levels decided in Tur 4
TEMAS_SEVIYELERI = (('basarili_v05', 0.5), ('basarili_v10', 1.0))


def temas_seviyeleri(oz):
    """{'basarili_v05': bool, 'basarili_v10': bool} for one ep_ozet."""
    v = oz.get('temas_dikey_hiz_gercek_hesap_mps')
    hiz_var = v is not None and math.isfinite(float(v))
    return {ad: bool(oz.get('basarili')) and hiz_var and float(v) < esik
            for ad, esik in TEMAS_SEVIYELERI}
