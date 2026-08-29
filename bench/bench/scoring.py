"""Confluence scoring — reduced-component port of Pine Section 15.

Ported components (same point values as LSS-Pro.pine v3.1.0):
    sweep grade            SSL→bull / BSL→bear   A=9 B=7 C=4
    FVG state              CE=7 / fresh|first=5 / deep=2   + post-sweep=3
    structure bias align   +4     (from the swing proxy, structure.py)
    active session         +2     (PoC: assumed always in-session)
    PDH/PDL sweep          +5
    inducement             +3
    RSI OS/OB              +3
    volume spike (dir)     +3
    VWAP alignment         +2
    rejection candle       +4     (needs bias == direction)

NOT ported (documented divergence — these add up to ~45 pts in the live
indicator, so PoC scores run LOWER than live and the threshold behaves
differently):
    HTF bias +6, HTF FVG +7/+4, HTF OB +6, BOS +4, CHoCH +7/+4,
    CHoCH+ +4, kill zone +4, PDH/PDL context +2, OTE +3/+5,
    news +5, pre-positioning +8, LTF order-block proximity +3.

`conf_threshold` is therefore lowered in run_poc via --threshold when
comparing; the baseline run also reports the score distribution so we can
recalibrate.
"""
from __future__ import annotations

import numpy as np

from .engine import BULL, BEAR, SWEEP_A, SWEEP_B, MITIGATED, CE_TOUCH, DEEP_RETEST


def _fvg_flags(fvgs):
    active = ps = ce = deep = False
    for f in fvgs:
        if f.state == MITIGATED:
            continue
        active = True
        ps = ps or f.post_sweep
        ce = ce or f.state == CE_TOUCH
        deep = deep or f.state == DEEP_RETEST
    return active, ps, ce, deep


def score_bar(v, eng, i) -> tuple[int, int]:
    """Return (bull_score, bear_score) for BarView v. `eng` = Engine (for series)."""
    bull = bear = 0

    if getattr(v, "recent_ssl_sweep", False):
        bull += 9 if v.last_ssl_grade == SWEEP_A else 7 if v.last_ssl_grade == SWEEP_B else 4
    if getattr(v, "recent_bsl_sweep", False):
        bear += 9 if v.last_bsl_grade == SWEEP_A else 7 if v.last_bsl_grade == SWEEP_B else 4

    b_active, b_ps, b_ce, b_deep = _fvg_flags(v.bull_fvgs)
    s_active, s_ps, s_ce, s_deep = _fvg_flags(v.bear_fvgs)
    if b_active:
        bull += 7 if b_ce else 2 if b_deep else 5
        if b_ps:
            bull += 3
    if s_active:
        bear += 7 if s_ce else 2 if s_deep else 5
        if s_ps:
            bear += 3

    if v.bias == BULL:
        bull += 4
    elif v.bias == BEAR:
        bear += 4

    # active session (PoC assumption)
    bull += 2
    bear += 2

    if v.pdl_swept:
        bull += 5
    if v.pdh_swept:
        bear += 5

    if v.indu_ssl:
        bull += 3
    if v.indu_bsl:
        bear += 3

    rsi = eng.rsi[i]
    if np.isfinite(rsi):
        if rsi <= eng.cfg.rsi_os:
            bull += 3
        if rsi >= eng.cfg.rsi_ob:
            bear += 3

    vsma = eng.vol_sma[i]
    if np.isfinite(vsma) and eng.v[i] > vsma * eng.cfg.vol_mult:
        c1 = eng._off(eng.c, i, 1)
        o1 = eng._off(eng.o, i, 1)
        if np.isfinite(c1):
            if c1 > o1:
                bull += 3
            elif c1 < o1:
                bear += 3

    vwap = eng.vwap[i]
    if np.isfinite(vwap):
        if eng.c[i] > vwap:
            bull += 2
        elif eng.c[i] < vwap:
            bear += 2

    # rejection candle on bar[1] (Pine 15.3)
    o1, h1, l1, c1 = (eng._off(a, i, 1) for a in (eng.o, eng.h, eng.l, eng.c))
    if np.isfinite(c1):
        rng = h1 - l1
        if rng > 0:
            if c1 > o1 and (c1 - l1) > rng * 0.6 and v.bias == BULL:
                bull += 4
            if c1 < o1 and (h1 - c1) > rng * 0.6 and v.bias == BEAR:
                bear += 4

    return bull, bear
