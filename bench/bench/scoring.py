"""Confluence scoring — full 0-100 port of Pine Section 15 (v3.1.0).

All 23 components ported. News (+5) and pre-positioning (+8) are stubbed to
0 for the first baseline (Section 11.5 not ported). In `volume_blind` mode
(index spot) the vol-spike (+3) and VWAP (+2) factors go neutral and the
sweep-grade volume factor is already dropped in engine._detect_sweeps, so
A-grade sweeps cap at 2 factors (→ B). Documented divergence.

Returns RAW (bull, bear) — Pine caps only the *displayed* conf_score; the
signal / entry gates compare the raw side score.
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
    cfg = eng.cfg
    bull = bear = 0

    # ── Sweep grade (A=9 B=7 C=4) ──────────────────────────────
    if v.recent_ssl_sweep:
        bull += 9 if v.last_ssl_grade == SWEEP_A else 7 if v.last_ssl_grade == SWEEP_B else 4
    if v.recent_bsl_sweep:
        bear += 9 if v.last_bsl_grade == SWEEP_A else 7 if v.last_bsl_grade == SWEEP_B else 4

    # ── FVG state (CE=7 / fresh|first=5 / deep=2) + post-sweep 3 ─
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

    # ── Structure BOS +4 / CHoCH +7 (+4 CHoCH+) ────────────────
    if v.recent_bos_bull:
        bull += 4
    if v.recent_bos_bear:
        bear += 4
    if v.recent_choch_bull:
        bull += 7
        if v.recent_choch_plus_bull:
            bull += 4
    if v.recent_choch_bear:
        bear += 7
        if v.recent_choch_plus_bear:
            bear += 4

    # ── Structure bias +4 ─────────────────────────────────────
    if v.bias == BULL:
        bull += 4
    elif v.bias == BEAR:
        bear += 4

    # ── HTF structure bias +6 ─────────────────────────────────
    if v.htf.bias == "Bullish":
        bull += 6
    elif v.htf.bias == "Bearish":
        bear += 6

    # ── Active session +2 both ────────────────────────────────
    if v.active_session:
        bull += 2
        bear += 2

    # ── Kill zone +4 both ─────────────────────────────────────
    if v.kill_zone:
        bull += 4
        bear += 4

    # ── Context PDH/PDL +2 ────────────────────────────────────
    if v.ctx_above:
        bull += 2
    if v.ctx_below:
        bear += 2

    # ── PDH/PDL sweep bonus +5 ────────────────────────────────
    if v.pdl_swept:
        bull += 5
    if v.pdh_swept:
        bear += 5

    # ── Inducement +3 ────────────────────────────────────────
    if v.indu_ssl:
        bull += 3
    if v.indu_bsl:
        bear += 3

    # ── RSI +3 (OS / OB or divergence) ───────────────────────
    rsi = eng.rsi[i]
    if (np.isfinite(rsi) and rsi <= cfg.rsi_os) or eng.rsi_bull_div[i]:
        bull += 3
    if (np.isfinite(rsi) and rsi >= cfg.rsi_ob) or eng.rsi_bear_div[i]:
        bear += 3

    # ── Volume spike +3 (skip volume-blind) ──────────────────
    if not cfg.volume_blind:
        vsma = eng.vol_sma[i]
        if np.isfinite(vsma) and eng.v[i] > vsma * cfg.vol_mult:
            c1 = eng._off(eng.c, i, 1)
            o1 = eng._off(eng.o, i, 1)
            if np.isfinite(c1):
                if c1 > o1:
                    bull += 3
                elif c1 < o1:
                    bear += 3

    # ── VWAP alignment +2 (skip volume-blind) ────────────────
    if not cfg.volume_blind:
        vwap = eng.vwap[i]
        if np.isfinite(vwap):
            if eng.c[i] > vwap:
                bull += 2
            elif eng.c[i] < vwap:
                bear += 2

    # ── News +5 / pre-positioning +8 — STUBBED (Section 11.5) ─

    # ── LTF Order Block proximity +3 ─────────────────────────
    if v.ob_bull_near:
        bull += 3
    if v.ob_bear_near:
        bear += 3

    # ── HTF FVG confluence (+7 CE near / +4 active) ──────────
    if v.htf.fvg_bull_active:
        bull += 7 if v.htf.fvg_bull_ce_near else 4
    if v.htf.fvg_bear_active:
        bear += 7 if v.htf.fvg_bear_ce_near else 4

    # ── HTF Order Block +6 ──────────────────────────────────
    if v.htf.ob_bull_near:
        bull += 6
    if v.htf.ob_bear_near:
        bear += 6

    # ── OTE (+3 price in zone / +5 FVG CE in zone) ───────────
    if v.ote_price_in_zone:
        if v.bias == BULL:
            bull += 3
        elif v.bias == BEAR:
            bear += 3
    if v.ote_fvg_ce_in:
        if v.bias == BULL:
            bull += 5
        elif v.bias == BEAR:
            bear += 5

    # ── Rejection candle +4 (bar[1] wick, bias-aligned) ──────
    o1, h1, l1, c1 = (eng._off(a, i, 1) for a in (eng.o, eng.h, eng.l, eng.c))
    if np.isfinite(c1):
        rng = h1 - l1
        if rng > 0:
            if c1 > o1 and (c1 - l1) > rng * 0.6 and v.bias == BULL:
                bull += 4
            if c1 < o1 and (h1 - c1) > rng * 0.6 and v.bias == BEAR:
                bear += 4

    return bull, bear
