"""Build bench/data/<instrument>_5m.csv from raw Kite JSON dumps.

Workflow for the free Kite-MCP path:
  1. In a Claude session, call `mcp__Kite__get_historical_data` in ~15-20 day
     windows (5minute). Large results are auto-saved to a tool-results file.
  2. Copy each dump into bench/data/raw/ as `<instrument>_<from>_<to>_<id>.json`
     (any name starting with the instrument tag works).
  3. Run:  python scripts/stitch.py crude      ->  data/crude_5m.csv

Dedups on timestamp, sorts, drops zero-volume bars for instruments that
have real volume (futures); keeps them for volume-less feeds (index spot).
"""
from __future__ import annotations

import glob
import json
import pathlib
import sys

import pandas as pd

RAW = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data"

# instruments whose feed carries no volume (Kite serves 0 for index spot)
VOLUMELESS = {"niftyspot", "banknifty", "nifty"}


def stitch(tag: str) -> pathlib.Path:
    files = sorted(glob.glob(str(RAW / f"{tag}*.json")))
    if not files:
        sys.exit(f"no raw files matching {RAW}/{tag}*.json")
    rows: list = []
    for f in files:
        d = json.load(open(f))
        if isinstance(d, list):
            rows.extend(d)
    df = pd.DataFrame(rows)[["date", "open", "high", "low", "close", "volume"]]
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    if tag.lower() not in VOLUMELESS:
        df = df[df["volume"] > 0].reset_index(drop=True)
    out = OUT / f"{tag}_5m.csv"
    df.to_csv(out, index=False)
    span = f"{df['date'].iloc[0]} .. {df['date'].iloc[-1]}"
    print(f"{out}  —  {len(df)} bars  ({span})  from {len(files)} dumps")
    return out


if __name__ == "__main__":
    stitch(sys.argv[1] if len(sys.argv) > 1 else "crude")
