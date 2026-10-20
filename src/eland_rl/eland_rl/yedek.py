"""Deadline fallback ("yedek iniş", amendment 21): an evaluation-time rule, like the shield, that works only from
what the vehicle has -- the observation's target channel, its height and the episode clock.

The policy does not see the clock, and most timeouts are landable with more time (B2-s0 + shield: 76.9 % at
30 s, 88.1 % at 90 s). So when the time left is no longer enough to descend from the current camera height to
the episode's end height at the descend speed, plus a margin, the policy is overridden:

  - the centre is safe in the target channel                -> descend (9)
  - a safe pixel is in view                                 -> towards the nearest one: a sliding descent
                                                               (10..17) if the model has them, else a slide (1..8)
  - nothing safe in view                                    -> the policy's own action

It never forces a descent onto ground the channel calls unsafe. A shield, if any, still acts after this rule.
"""
from .pilots import centre_safe, towards_nearest_safe

PAY_S = 2.0         # margin over the pure descent time: command delay, PX4's lag, acceleration (pre-registered)


def gerekli_sure(yukseklik_m, hedef_m=5.0, v_alcal=2.0, pay_s=PAY_S):
    """Seconds needed to reach the episode's end height from yukseklik_m at the descend speed, plus the margin."""
    return max(yukseklik_m - hedef_m, 0.0) / v_alcal + pay_s


def yedek(action, obs, yukseklik_m, t, max_t, diag, hedef_m=5.0, v_alcal=2.0, pay_s=PAY_S):
    """(action, overridden). obs is the 3+ channel observation (channel 2 = target / SORA-safe mask)."""
    if max_t - t > gerekli_sure(yukseklik_m, hedef_m, v_alcal, pay_s):
        return action, False
    if centre_safe(obs):
        return 9, action != 9
    a = towards_nearest_safe(obs)
    if a == 0:
        return action, False
    a = a + 9 if diag else a
    return a, a != action
