# LSS Pro — Liquidity Sweep System

A professional-grade TradingView indicator built on Smart Money Concepts (SMC) / ICT methodology.

LSS Pro is not just another liquidity sweep indicator — it's a complete institutional trading framework that detects liquidity sweeps, fair value gaps, market structure breaks, and higher-timeframe context, then scores every trade setup by confluence on a clean 0–100 scale before generating entries.

---

## Current Version: v3.1.1 — Scoring-integrity fixes

**Status:** Phase 4 complete; v3.1.1 patch fixes the scoring bugs found in review (HTF FVG/OB indexing, score cap, dashboard colour bands, win-rate expectancy).
**Active file:** [`LSS-Pro-v3_1_1.pine`](LSS-Pro-v3_1_1.pine) (branch `develop`)
**Next:** Phase 5 — Signal Quality & Visualization (see [Roadmap](#roadmap) and the [handover doc](LSS-Pro-v3_1_0-handover.md)).

### Engines Live

| Section | Engine | Since |
|---------|--------|-------|
| 6 | HTF Structure Engine — real swing high/low bias via `request.security` (replaces EMA proxy) | v3.0.0 |
| 6B | HTF FVG & Order Block Engine — 3-candle HTF FVG, OB body zone, CE proximity | v3.0.0 |
| 11.5 | News Calendar — instrument-aware (EIA Crude / API Crude / EIA Nat Gas / manual) | v2.7.1 |
| 11.6 | News Pre-Positioning — captures HTF bias in the pre-news window, confirms on post-news sweep | v3.1.0 |
| 12 | Liquidity — BSL/SSL detection, sweep grading A/B/C, PDH/PDL bonus, inducement | v2.7.0 |
| 12.5 | Displacement Detection — body %, range/ATR, volume/SMA → NONE / NORMAL / STRONG | v2.7.0 |
| 13 | FVG Engine — 5-state (Fresh → First Touch → CE Touch → Deep Retest → Mitigated) | v2.7.0 |
| 13B | Order Block Engine — border-only visuals | v2.7.0 |
| 14 | Market Structure — BOS / CHoCH / CHoCH+, structure bias, counter-trend FVG purge | v2.7.0 |
| 14.9 | Fibonacci OTE Zone — 50–70.5% retracement, adaptive lookback, ▲/▼ label | v2.7.1 |
| 15 | Confluence Scoring — rescaled 0–100, 23 components, tiered weights | v3.1.0 |
| 16 | Setup Lifecycle — pending → active, CE-touch close confirmation, news gate | v2.6.0 |
| 17 | Win-Rate Tracker — TP2 / TP1+BE / SL counters, Win %, Total R, Avg R, Expectancy, Avg Score | v3.1.0 |
| 9 | Dashboard — 28 rows, full HTF block at top | v3.0.0 |
| 11 | Alerts — score-gated (sweep, CE, CHoCH bull/bear) + pre-positioning bull/bear | v3.1.0 |

### Companion Tool — LSS News Monitor

A separate Python + GitHub Actions service (private repo `Sriram0919/lss-news-monitor`) polls 14 RSS feeds every 10 minutes, 24/7, and pushes Telegram alerts for crude oil (EIA, API, OPEC, geopolitical) and India market events (RBI, Nifty/Sensex, macro, corporate events). It runs independently of the Pine indicator. See [`news-monitor-update.md`](news-monitor-update.md) for the latest coverage changes.

---

## Confluence Scoring — v3.1.0 (0–100)

23 weighted components across four tiers. Trades fire only when the score clears the configurable minimum, and alerts are score-gated on top of that.

| Tier | Weight | Key factors |
|------|--------|-------------|
| Core ICT | ~50 | Sweep grade A/B/C (9/7/4), FVG CE touch (7), Structure CHoCH (7) / BOS (4), CHoCH+ bonus (4) |
| HTF Alignment | ~25 | HTF structure bias (6), HTF FVG active at CE (7), HTF OB in zone (6), Session bias (4) |
| Quality Markers | ~15 | PDH/PDL sweep (5), OTE FVG CE in zone (5), Rejection candle (4), Inducement (3), OTE in zone (3) |
| Supporting | ~10 | Pre-positioning bonus (8), News post-sweep bonus (5), RSI (3), Volume spike (3), OB proximity (3), Kill Zone (2), VWAP (2) |

> v3.1.1: score is now capped at 100 and the dashboard colour bands were realigned to 70/55/40/25. Remaining review items (RSI divergence polarity, line-object leak, duplicated displacement math, alert placeholder) are tracked in the [handover doc](LSS-Pro-v3_1_0-handover.md#5-known-bugs--pending-issues).

---

## Roadmap

| Version | Module | Status |
|---------|--------|--------|
| v2.0.1 | Foundation (Session / HTF / Trend / Context) | Done |
| v2.1.0 | Liquidity Engine (BSL/SSL, EQH/EQL, sweeps) | Done |
| v2.2.0 | FVG Engine (impulse-filtered) | Done |
| v2.3.0 | Market Structure Engine (BOS / CHoCH) | Done |
| v2.4.0 | Confluence Scoring Engine (RSI / Volume / VWAP) | Done |
| v2.7.0 | Sweep grading, displacement, 5-state FVG, OB engine, setup lifecycle | Done |
| v2.7.1 | Instrument-aware news filter, adaptive OTE lookback | Done |
| v3.0.0 | MTF Intelligence — real HTF structure, HTF FVG/OB, HTF-weighted scoring | Done |
| v3.1.0 | Score rescale 0–100, win-rate tracker, score-gated alerts, news pre-positioning | Done |
| v3.1.1 | Scoring-integrity fixes (HTF FVG/OB indexing, score cap, dashboard bands, expectancy) | Done |
| v3.2 / Phase 5 | Signal quality gates + weekly/HTF level visualization | Next |

### Phase 5 targets

- Sweep-to-FVG distance filter; entry-candle quality gate
- Session-aware ATR stop-loss multiplier
- LTF+HTF FVG stack bonus; premium/discount equilibrium filter
- Consecutive-loss suppression guard; range/trend regime filter (ATR percentile)
- Weekly High/Low lines and HTF swing level lines drawn on the chart

---

## How It Works

LSS Pro is built in layers. Each layer feeds the next:

```
Layer 1: Context      Session → HTF Structure → HTF FVG/OB → Previous Day H/L
                                      ↓
Layer 2: Detection    Liquidity → Displacement → FVG → Order Blocks → Market Structure → OTE
                                      ↓
Layer 3: Intelligence Confluence Scoring (0–100 from all detections + HTF alignment + news)
                                      ↓
Layer 4: Output       Setup Lifecycle → score-gated entries, SL / TP1 / TP2, Win-Rate Tracker
```

The Confluence Scoring Engine is the core differentiator. Instead of binary BUY/SELL signals it produces a weighted 0–100 score, and setups only fire above a configurable threshold.

---

## Setup

1. Open TradingView → Pine Editor
2. Paste the contents of [`LSS-Pro-v3_1_1.pine`](LSS-Pro-v3_1_1.pine)
3. Click **Add to Chart**
4. Primary test instrument: **MCX Crude Oil 5m**. Also works on NIFTY / BANKNIFTY 5m and crypto (BTCUSDT / ETHUSDT) for after-hours testing.

Use TradingView's **Bar Replay** to test on historical data when markets are closed.

### Key Settings

- **Alert Min Score** — minimum confluence score before signals and alerts fire
- **Swing Lookback** — bars on each side of a pivot (also scales OTE lookback by timeframe)
- **EQH/EQL Tolerance** — tick threshold for equal high/low classification
- **News source** — auto (EIA Crude / API Crude / EIA Nat Gas by instrument) or manual
- **Show/Hide** — BSL, SSL, FVG, OB, OTE, EMAs, PDH/PDL, Dashboard, Debug toggled independently
- **HTF Mode** — auto-mapping (1m→15m, 5m→1H, …) or manual override
- **Dashboard Position** — any corner

---

## Design Principles

- **No repainting** — all detections use confirmed bars only; `request.security` calls use `lookahead = barmerge.lookahead_off`
- **Modular architecture** — each engine is an independent section with a fixed data-flow order
- **Performance first** — reuse labels, tables, lines; minimize `request.security()` calls
- **No duplicated logic** — one responsibility per function
- **Professional variable names** — no magic numbers

---

## Repository Structure

```
Liquidity-Sweep-System/
  LSS-Pro-v3_1_1.pine            # active indicator (single file, ~4,000 lines)
  LSS-Pro-v3_1_0-handover.md     # current session handover — read this first
  LSS-Pro-v3_0_0-handover.md     # historical handover
  LSS-Pro-v2.7.0-handover.md     # historical handover
  LSS-Pro-v2.5.0.pine            # archived v2.7.1 code (filename retained by convention)
  news-monitor-update.md         # companion News Monitor coverage changes
  My_ideas.rtf                   # user feature backlog
  src/                           # archived early engine builds (v2.1.0 – v2.4.0)
  docs/Architecture.md
  README.md
  CHANGELOG.md
```

---

## Branch Strategy

- `main` — stable releases only
- `develop` — integration branch, all development happens here
- `feature/*` — individual engine branches (merged into develop)

---

## Author

**Sriram0919** — [GitHub](https://github.com/Sriram0919)

## License

Private — All rights reserved.
