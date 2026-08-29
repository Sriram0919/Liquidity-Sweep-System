"""Section 14.9 — Fibonacci OTE (Optimal Trade Entry) zone.

Port of LSS-Pro.pine Section 14.8.1 / 14.8.2. Cheap arithmetic over the
recent swing: 50%–70.5% retracement, 61.8% ideal entry.

`_ote_tf_mult` for a 5m chart = 16, so `ote_lookback = ms_swing_lb * 16`.
"""
from __future__ import annotations

import numpy as np

from .market_structure import BULL, BEAR


def precompute(h: np.ndarray, l: np.ndarray, lookback: int):
    """Rolling highest/lowest + their bar offsets (Pine ta.highest/highestbars).

    Returns (recent_high, recent_low, high_off, low_off) where *_off is a
    non-positive int: 0 = current bar, -k = k bars ago (== ta.highestbars).
    """
    n = len(h)
    rh = np.full(n, np.nan)
    rl = np.full(n, np.nan)
    ho = np.zeros(n, dtype=int)
    lo = np.zeros(n, dtype=int)
    for i in range(n):
        s = max(0, i - lookback + 1)
        wh = h[s:i + 1]
        wl = l[s:i + 1]
        # Pine ta.highestbars: most RECENT occurrence of the extreme
        hj = len(wh) - 1 - int(np.argmax(wh[::-1]))
        lj = len(wl) - 1 - int(np.argmin(wl[::-1]))
        rh[i] = wh[hj]
        rl[i] = wl[lj]
        ho[i] = -(len(wh) - 1 - hj)
        lo[i] = -(len(wl) - 1 - lj)
    return rh, rl, ho, lo


def ote_zone(bias, recent_high, recent_low, high_off, low_off):
    """Return (ote_high, ote_low, ote_618) or (nan, nan, nan)."""
    rng = recent_high - recent_low
    if not np.isfinite(rng) or rng <= 0:
        return np.nan, np.nan, np.nan
    if bias == BEAR and high_off < low_off:
        return (recent_low + rng * 0.705,
                recent_low + rng * 0.500,
                recent_low + rng * 0.618)
    if bias == BULL and low_off < high_off:
        return (recent_high - rng * 0.500,
                recent_high - rng * 0.705,
                recent_high - rng * 0.618)
    return np.nan, np.nan, np.nan
