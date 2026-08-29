# LSS Pro — Python Backtest Bench (plan)

_Decision recorded 2026-08-29. Not started yet._

## The problem

LSS Pro runs in Pine Script on TradingView. Pine can't be compiled or tested
locally, has hard caps (hit the 64-plot limit in v3.2.0), is single-file, and
has no debugger or unit tests. More importantly: **there is no backtest.** The
Win-Rate Tracker (Section 17) collects closed trades one bar at a time, so
getting a statistically meaningful sample takes months of live running.

Phase 5 is eight signal-quality filters (premium/discount, regime gate,
sweep-to-FVG distance, entry-candle gate, session ATR SL, LTF+HTF FVG stack,
consecutive-loss guard, day/time filter). Each one is a bet that it improves
the edge — and some will hurt. In Pine we can't measure which. In a backtest
we can: baseline expectancy → add filter → measure delta on years of data.

## The decision

**Build a Python backtest bench before implementing the Phase 5 filters.
Keep the Pine indicator as the live chart + alert layer — same logic, two homes.**

This is not a rewrite of the product. Pine stays. Python becomes the R&D /
validation environment.

## Scope

- **Port the scoring engine to Python** — it's arithmetic on OHLCV + pivots
  (sweep grading, FVG states, market structure, HTF bias, the 0–100 confluence
  score). Translates cleanly from Pine.
- **Data:** Zerodha **Kite Connect** historical candles (already have access;
  Kite MCP also available). MCX Crude 5m primary, BankNifty 5m secondary.
- **Engine:** `backtesting.py` or `vectorbt` (both free/open-source).
- **Charting:** `plotly` / `mplfinance` / TradingView **Lightweight Charts**
  (free) — candles + our own overlays, no plot caps.
- **Output:** win %, expectancy (R), max drawdown, trade count, equity curve,
  parameter sweeps.

## Cost

- Software: **free** (all open-source libraries).
- Data: **~₹500/month** for Kite Connect, or free via Kite MCP — likely
  already covered.
- Main cost is **time**: ~3–4 focused sessions for the engine port + harness.

## Sequence

1. ✅ Phase 5 visualization — done (v3.2.0: weekly H/L + HTF swing lines).
2. **Pause new Pine features.**
3. **Proof of concept** — port just sweep + FVG + scoring core, run on ~6 months
   of Crude 5m from Kite, produce a baseline win-rate. Decide if the full port
   is worth it. *(Offered — not yet started.)*
4. Full engine port + backtest harness → baseline metrics on 2+ years.
5. Add each Phase 5 filter **in Python first**, measure the delta, keep winners.
6. Port the winning filter set back to Pine in **one batch** for the live chart.

## Status

| Step | State |
|---|---|
| Decision recorded | ✅ 2026-08-29 |
| Proof of concept | ✅ 2026-08-29 — `bench/`, see `bench/POC-FINDINGS.md` |
| Full engine port | ⬜ next — revised scope in POC-FINDINGS (add Section 14, 6/6B, 16.7, 14.9) |
| Baseline metrics | ⬜ blocked on full port + 2yr data |
| Phase 5 filters evaluated in Python | ⬜ |
| Winning set ported back to Pine | ⬜ |

**PoC outcome:** pipeline works on real MCX Crude 5m data (Jun–Aug 2026,
7.6k candles). Port translates cleanly. But the "sweep + FVG + scoring core"
scope omits the components that gate/generate live trades — reduced score
tops out at 36/100 (live threshold 55 admits nothing) and the
confluence-signal-only entry path yields ~5 trades/3mo. Section 14 (BOS/
CHoCH), 6/6B (HTF) and 16.7 (FVG-retest pipeline) are **not optional**.

## Open questions

- **Data source — OPEN, blocks the baseline.** Tested 2026-08-29: the free
  Kite MCP serves only currently-active instruments in ~20-day windows;
  `continuous=true` and expired contracts both fail. So:
  - MCX CRUDEOIL SEP future → ~6 clean weeks (liquid from mid-July; June is
    mostly volume=0 placeholders).
  - NSE:NIFTY BANK spot → 2+ years of 5m, but **volume always 0** (kills the
    displacement gate + volume/sweep-grade/vol-spike/VWAP score components).
  - Index/stock futures → current unexpired contract only (~2–3 months).
  Options: (a) Kite Connect SDK paid (~₹2k/mo historical) for 2yr Crude 5m
  with volume + continuous stitching; (b) run the baseline on BankNifty spot
  with volume components stubbed; (c) another data vendor.  **User decision
  pending.**
- `backtesting.py` (simpler, single-asset, event-driven) vs `vectorbt`
  (faster, vectorised, better for parameter sweeps) — pick after the PoC.
- Trade model: the Pine engine uses TP1/TP2/BE with `IN_TRADE_TP1_RR` /
  `IN_TRADE_TP2_RR` — replicate that exit logic exactly so numbers are
  comparable to the live Win-Rate Tracker.
