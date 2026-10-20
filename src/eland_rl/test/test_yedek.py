"""Amendment 21: deadline fallback (eland_rl.yedek)."""
import numpy as np
import pytest

from eland_rl.yedek import PAY_S, gerekli_sure, yedek


def gozlem(safe_rc=None):
    """A 3x128x128 observation whose channel 2 (target mask) is safe only at the given (row, col) block."""
    o = np.zeros((3, 128, 128), np.float32)
    if safe_rc is not None:
        r, c = safe_rc
        o[2, r:r + 4, c:c + 4] = 1.0
    return o


def test_gerekli_sure():
    assert gerekli_sure(25.0) == pytest.approx(10.0 + PAY_S)
    assert gerekli_sure(5.0) == pytest.approx(PAY_S)
    assert gerekli_sure(3.0) == pytest.approx(PAY_S)        # below the end height: only the margin


def test_zaman_varken_politikaya_dokunmaz():
    a, m = yedek(3, gozlem((62, 62)), 25.0, t=10.0, max_t=30.0, diag=True)    # 20 s left > 12 s needed
    assert (a, m) == (3, False)


def test_merkez_guvenliyse_alcalir():
    a, m = yedek(0, gozlem((62, 62)), 25.0, t=19.0, max_t=30.0, diag=False)   # 11 s left <= 12 s needed
    assert (a, m) == (9, True)


def test_guvenli_piksele_kayarak_alcalir():
    # safe block straight ahead (image up = nose = lateral action 1); sliding descent of action 1 is 10
    a, m = yedek(0, gozlem((10, 62)), 25.0, t=19.0, max_t=30.0, diag=True)
    assert (a, m) == (10, True)
    a, m = yedek(0, gozlem((10, 62)), 25.0, t=19.0, max_t=30.0, diag=False)
    assert (a, m) == (1, True)


def test_guvenli_yer_yoksa_politika_kalir_ve_guvensize_zorla_inmez():
    a, m = yedek(5, gozlem(None), 25.0, t=29.0, max_t=30.0, diag=True)
    assert (a, m) == (5, False)
    a, m = yedek(9, gozlem(None), 25.0, t=29.0, max_t=30.0, diag=True)   # the policy's own descent stays
    assert (a, m) == (9, False)
