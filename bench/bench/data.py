"""Candle IO.

The bench reads CSVs from bench/data/. Kite Connect historical candles are
fetched out-of-band (via the Kite MCP tools in a Claude session, or the
kiteconnect SDK) and dumped here with `write_candles()`.

CSV schema: date,open,high,low,close,volume   (date = ISO8601, tz-aware)
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
COLS = ["date", "open", "high", "low", "close", "volume"]


def write_candles(rows: list, path: str | pathlib.Path) -> pathlib.Path:
    """rows: Kite-style [[date, o, h, l, c, v], ...] or list of dicts."""
    if rows and isinstance(rows[0], dict):
        df = pd.DataFrame(rows)[COLS]
    else:
        df = pd.DataFrame(rows, columns=COLS)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def load_candles(path: str | pathlib.Path) -> pd.DataFrame:
    path = pathlib.Path(path)
    if not path.is_absolute() and not path.exists():
        path = DATA_DIR / path.name
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.set_index("date", drop=False)
    return df


def synthetic_candles(bars: int = 6000, seed: int = 7, freq: str = "5min") -> pd.DataFrame:
    """Smoke-test data: random walk with intraday sessions and volume noise.

    NOT for real metrics — only so the pipeline runs before Kite data lands.
    """
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-02-02 09:00", tz="UTC")
    idx = pd.date_range(start, periods=bars, freq=freq)
    step = rng.normal(0, 1.0, bars)
    # inject occasional 3-bar impulse legs so FVGs actually form
    for k in rng.integers(5, bars - 5, size=bars // 60):
        step[k : k + 3] += rng.choice([-1, 1]) * rng.uniform(6, 12)
    close = 6000 + step.cumsum() + 15 * np.sin(np.arange(bars) / 90.0)
    spread = rng.uniform(0.5, 2.5, bars)
    op = np.r_[close[0], close[:-1]]
    hi = np.maximum(op, close) + spread
    lo = np.minimum(op, close) - spread
    vol = rng.lognormal(9.0, 0.5, bars)
    df = pd.DataFrame(
        {"date": idx, "open": op, "high": hi, "low": lo, "close": close, "volume": vol}
    ).set_index("date", drop=False)
    return df
