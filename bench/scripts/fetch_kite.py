"""Pull MCX Crude Oil 5m history into bench/data/.

Two ways to get candles in:

1) Kite MCP (what this repo uses in a Claude session)
   - `mcp__Kite__search_instruments` to resolve the instrument_token for the
     front-month MCX CRUDEOIL future (e.g. "CRUDEOIL24SEPFUT").
   - `mcp__Kite__get_historical_data` in <= ~60-day windows (Kite caps the
     range per request for intraday), interval="5minute".
   - Concatenate the windows and hand the rows to `bench.data.write_candles`.

2) kiteconnect SDK (standalone, needs an API key + access token)

       from kiteconnect import KiteConnect
       kc = KiteConnect(api_key=API_KEY); kc.set_access_token(ACCESS_TOKEN)
       rows = kc.historical_data(TOKEN, FROM, TO, "5minute")
       from bench.data import write_candles
       write_candles(rows, "bench/data/mcx_crude_5m.csv")

Open question (Backtest-Bench-Plan.md): how far back Kite serves 5m for MCX
futures — continuous-contract stitching across expiries may be needed for a
2+ year sample.
"""
from __future__ import annotations

import sys

from bench.data import write_candles


def from_mcp_windows(windows: list[list]) -> None:
    """windows: list of Kite get_historical_data 'candles' arrays, in order."""
    rows: list = []
    for w in windows:
        rows.extend(w)
    path = write_candles(rows, "bench/data/mcx_crude_5m.csv")
    print(f"wrote {len(rows)} candles -> {path}")


if __name__ == "__main__":
    print(__doc__)
    sys.exit(0)
