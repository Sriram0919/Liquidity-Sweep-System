"""Free 2-year 1h history for a basket of NSE tickers, via yfinance.

No auth. Yahoo serves 60m data for ~2y (anything sub-hour is capped at
60 days). Individual stocks carry REAL volume — this restores the
displacement gate + volume/VWAP/sweep-grade scoring that the volume-blind
BankNifty-spot feed disabled.

    cd bench && .venv/bin/python scripts/fetch_yf.py           # default basket
    cd bench && .venv/bin/python scripts/fetch_yf.py RELIANCE.NS INFY.NS

Writes bench/data/pool/<TICKER>.csv  (date=UTC ISO8601, standard schema).
Run the pooled backtest with:  scripts/phase5.py --pool
"""
from __future__ import annotations

import sys
import pathlib
import warnings

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "pool"

# liquid NSE names — real volume; + a few indices (volume-blind but the
# price structure is still valid for filter ranking)
DEFAULT = [
    "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
    "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS", "LT.NS", "BHARTIARTL.NS",
    "ITC.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "MARUTI.NS", "TATAMOTORS.NS",
    "SUNPHARMA.NS", "TITAN.NS", "ADANIENT.NS", "HCLTECH.NS", "WIPRO.NS",
    "TATASTEEL.NS", "JSWSTEEL.NS", "POWERGRID.NS", "NTPC.NS", "M&M.NS",
    "^NSEI", "^NSEBANK",
]


def fetch(ticker: str, interval: str = "60m", period: str = "2y",
         subdir: str = "") -> pathlib.Path | None:
    d = yf.download(ticker, period=period, interval=interval,
                    progress=False, auto_adjust=False)
    if d is None or len(d) == 0:
        print(f"{ticker:14} EMPTY — skipped")
        return None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.reset_index()
    d.columns = [str(c).lower() for c in d.columns]
    tcol = next(c for c in ("datetime", "date", "index") if c in d.columns)
    df = pd.DataFrame({
        "date": pd.to_datetime(d[tcol], utc=True),
        "open": d["open"], "high": d["high"], "low": d["low"],
        "close": d["close"], "volume": d["volume"].fillna(0),
    }).dropna(subset=["open"]).sort_values("date").drop_duplicates("date")
    outdir = OUT.parent / subdir if subdir else OUT
    outdir.mkdir(parents=True, exist_ok=True)
    tag = ticker.replace("^", "").replace(".NS", "").replace("&", "")
    out = outdir / f"{tag}.csv"
    df.to_csv(out, index=False)
    v = int(df["volume"].sum())
    print(f"{ticker:14} {len(df):5} bars  {str(df['date'].iloc[0])[:10]} .. "
          f"{str(df['date'].iloc[-1])[:10]}  {'vol' if v else 'NO-vol'}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--5m":
        # 60-day 5m cross-check pool (Yahoo caps sub-hour history at 60d)
        tickers = args[1:] or DEFAULT
        n = sum(fetch(t, "5m", "60d", "pool5m") is not None for t in tickers)
        print(f"\n{n}/{len(tickers)} written to {OUT.parent / 'pool5m'}")
    else:
        tickers = args or DEFAULT
        n = sum(fetch(t) is not None for t in tickers)
        print(f"\n{n}/{len(tickers)} written to {OUT}")
