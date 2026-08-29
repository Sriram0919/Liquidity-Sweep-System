"""How to get MCX Crude (or other) 5m history into bench/data/.

═══════════════════════════════════════════════════════════════════════
KITE MCP (free) — what actually works, learned 2026-08-29
═══════════════════════════════════════════════════════════════════════
`mcp__Kite__get_historical_data(instrument_token, "5minute", from, to)`

WORKS:
  * currently-ACTIVE instruments only
  * ~15-25 day windows per call (longer -> "Failed to get historical data")
  * large results auto-save to a tool-results .txt (never fit in context) —
    copy them to bench/data/raw/ and run scripts/stitch.py

DOES NOT WORK:
  * expired derivative contracts        -> "Failed to get historical data"
  * continuous=true (back-adjusted)     -> "Failed to get historical data"

CONSEQUENCE — the free path can't build a multi-year 5m sample:
  * MCX CRUDEOIL26SEPFUT (token 144870151): its own contract history only.
    Real liquidity from ~mid-July 2026; June bars are mostly volume=0
    placeholders; nothing usable before ~June. => ~6 clean weeks.
  * NSE:NIFTY BANK spot (token 260105): 2+ years of 5m OHLC available,
    BUT volume is always 0 -> disables LSS Pro's displacement gate + the
    volume/sweep-grade/vol-spike/VWAP scoring components.
  * BANKNIFTY / NIFTY futures: near-month is liquid from listing, but that
    is still only the current unexpired contract (~2-3 months).

So: full-fidelity + long history needs Kite Connect (paid) OR another vendor.

═══════════════════════════════════════════════════════════════════════
KITE CONNECT SDK (paid) — the clean path
═══════════════════════════════════════════════════════════════════════
    pip install kiteconnect
    from kiteconnect import KiteConnect
    kc = KiteConnect(api_key=API_KEY); kc.set_access_token(ACCESS_TOKEN)
    # continuous=True stitches across expiries for a back-adjusted series
    rows = kc.historical_data(TOKEN, FROM, TO, "5minute", continuous=True)
    from bench.data import write_candles
    write_candles(rows, "bench/data/crude_5m.csv")

Put API_KEY / ACCESS_TOKEN in bench/.env (git-ignored). access_token
expires ~6 AM IST daily; regenerate via the login -> request_token flow.

Instrument tokens (resolved 2026-08-29 via mcp__Kite__search_instruments):
    MCX:CRUDEOIL26SEPFUT   144870151
    NSE:NIFTY BANK (spot)  260105
    NFO:BANKNIFTY26SEPFUT  17507842
"""
import sys

if __name__ == "__main__":
    print(__doc__)
    sys.exit(0)
