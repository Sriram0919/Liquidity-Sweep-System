"""Bar-series indicators, matching Pine's `ta.*` semantics.

Pine uses Wilder's RMA for `ta.atr` and `ta.rsi`; we replicate that, not a
simple rolling mean. Pivots follow `ta.pivothigh(src, L, R)`: a pivot is
confirmed R bars later and its value is `src` at the pivot bar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rma(s: pd.Series, length: int) -> pd.Series:
    """Wilder's moving average (Pine `ta.rma`)."""
    alpha = 1.0 / length
    return s.ewm(alpha=alpha, adjust=False, min_periods=length).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return rma(true_range(df), length)


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    out[avg_loss == 0] = 100.0
    return out


def sma(s: pd.Series, length: int) -> pd.Series:
    return s.rolling(length, min_periods=length).mean()


def session_vwap(df: pd.DataFrame) -> pd.Series:
    """Session-anchored VWAP (Pine 15.1): resets each calendar day."""
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    day = df.index.normalize() if isinstance(df.index, pd.DatetimeIndex) else df["date"].dt.normalize()
    cum_vol = df["volume"].groupby(day).cumsum()
    cum_tp_vol = (tp * df["volume"]).groupby(day).cumsum()
    out = cum_tp_vol / cum_vol
    return out.where(cum_vol > 0, df["close"])


def rsi_divergence(df: pd.DataFrame, rsi_ser, div_lb: int = 5):
    """Pine 15.1 Bug-H port — pivot-to-pivot RSI divergence.

    Confirm a price pivot (div_lb/div_lb legs), sample RSI at that pivot bar,
    compare price + RSI to the previous confirmed pivot of the same kind.
    Returns (bull_div, bear_div) bool numpy arrays, event-style (True only on
    the confirmation bar).
    """
    pl = pivot_low(df["low"], div_lb, div_lb).to_numpy()
    ph = pivot_high(df["high"], div_lb, div_lb).to_numpy()
    rsi = np.asarray(rsi_ser, float)
    n = len(rsi)
    bull = np.zeros(n, bool)
    bear = np.zeros(n, bool)
    prev_pl_px = prev_pl_rsi = None
    prev_ph_px = prev_ph_rsi = None
    for i in range(n):
        if np.isfinite(pl[i]):
            r = rsi[i - div_lb] if i - div_lb >= 0 else np.nan
            if prev_pl_px is not None and pl[i] < prev_pl_px and np.isfinite(r) and r > prev_pl_rsi:
                bull[i] = True
            prev_pl_px, prev_pl_rsi = pl[i], r
        if np.isfinite(ph[i]):
            r = rsi[i - div_lb] if i - div_lb >= 0 else np.nan
            if prev_ph_px is not None and ph[i] > prev_ph_px and np.isfinite(r) and r < prev_ph_rsi:
                bear[i] = True
            prev_ph_px, prev_ph_rsi = ph[i], r
    return bull, bear


def pivot_high(high: pd.Series, left: int, right: int) -> pd.Series:
    """`ta.pivothigh`: value placed on the CONFIRMATION bar (pivot bar + right)."""
    h = high.to_numpy()
    n = len(h)
    out = np.full(n, np.nan)
    for i in range(left, n - right):
        w = h[i - left : i + right + 1]
        if h[i] == w.max() and (w == h[i]).sum() == 1:
            out[i + right] = h[i]
    return pd.Series(out, index=high.index)


def pivot_low(low: pd.Series, left: int, right: int) -> pd.Series:
    lo = low.to_numpy()
    n = len(lo)
    out = np.full(n, np.nan)
    for i in range(left, n - right):
        w = lo[i - left : i + right + 1]
        if lo[i] == w.min() and (w == lo[i]).sum() == 1:
            out[i + right] = lo[i]
    return pd.Series(out, index=low.index)
