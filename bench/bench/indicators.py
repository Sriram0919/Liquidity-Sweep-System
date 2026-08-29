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
