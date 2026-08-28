# Changelog

All notable changes to LSS Pro are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [3.1.0] — 2026-08-21

Phase 4 — score rescale, win-rate tracking, news pre-positioning. File: `LSS-Pro-v3_1_0.pine`. Compiled clean on MCX Crude Oil 5m.

### Added
- **News Pre-Positioning Engine (Section 11.6)** — captures HTF bias during the pre-news window and confirms it on a post-news sweep; fires `ALT_PREPOS_BULL` / `ALT_PREPOS_BEAR` with a +8 score bonus
- **Win-Rate Tracker (Section 17)** — logs every closed trade (TP2 / TP1+BE / SL) to a dashboard block: Win %, Total R, Avg R, Expectancy, Avg Score at entry
- **Score-gated alerts** — `ALT_SWEEP`, `ALT_CE`, `ALT_CHOCH` (bull/bear) fire only when the confluence score ≥ `IN_ALERT_MIN_SCORE`

### Changed
- **Confluence score rescaled from ~225 to a clean 0–100 scale** — 23 components, tiered weights (Core ICT ~50 / HTF Alignment ~25 / Quality Markers ~15 / Supporting ~10)
- Dashboard expanded and score display switched to `/100`
- `fn_clear_trade_visuals()` now also runs on `TRADE_BE_HIT`

### Known issues (carried into Phase 5)
- HTF security indexing in Section 6B (`HTF_HIGH[2]` is chart-bars, not HTF-bars) makes ~13 points of HTF scoring unreliable
- Theoretical score max can reach ~109; not yet capped
- Some dashboard colour thresholds still calibrated for the old ~285 scale
- Win-rate expectancy formula double-subtracts losses

### Companion
- **LSS News Monitor** (separate repo) went live — Python + RSS + GitHub Actions cron `*/10 * * * *`, Telegram alerts for crude oil and India market events

---

## [3.0.0] — 2026-08-16

Phase 3 — MTF Intelligence. Real higher-timeframe structure replaces the EMA crossover proxy.

### Added
- **HTF Structure Engine (Section 6)** — HTF swing highs/lows via `request.security` with `ta.pivothigh` / `ta.pivotlow`; `HTF_BIAS` derived from HTF close vs last confirmed pivot (non-repainting)
- **HTF FVG & Order Block Engine (Section 6B)** — 3-candle HTF fair value gap detection, HTF OB body zone, CE proximity checks feeding the score
- Dashboard HTF block (bias, last SH/SL, HTF FVG/OB state) moved to the top

### Changed
- `HTF trend alignment` score factor now driven by real HTF structure instead of EMA 50/200 crossover
- `TREND_STATE` kept as an alias for `HTF_BIAS` so existing alerts/debug compile unchanged
- `ATR_VAL` moved above Section 6B (was in Section 13) — fixes an undeclared-identifier error
- HTF FVG boxes intentionally not drawn (span 12+ LTF candles, cluttered the 5m chart) — HTF context lives in the dashboard and score only

---

## [2.7.1] — 2026-08-16

### Added
- **Instrument-aware news filter** — `IS_CRUDE` / `IS_NATGAS` / `IS_EQUITY` detection; EIA/API crude events no longer block setups on unrelated instruments
- **Adaptive OTE lookback** — `IN_MS_SWING_LB × mult` where mult is 16 / 12 / 8 / 6 for ≤5m / ≤30m / ≤4H / daily+
- OTE zone box shows ▲/▼ direction label

### Fixed
- Bullish Fibonacci OTE math verified and annotated

---

## [2.7.0] — 2026-08-13

Sweep grading, displacement, stateful FVG, order blocks, and setup lifecycle.

### Added
- **Sweep grading A/B/C** on liquidity sweeps, with PDH/PDL bonus and inducement (double-sweep) detection
- **Displacement Detection (Section 12.5)** — body %, range/ATR, volume/SMA → NONE / NORMAL / STRONG
- **5-state FVG Engine** — Fresh → First Touch → CE Touch → Deep Retest → Mitigated (states are strings)
- **Order Block Engine (Section 13B)** — border-only zones off displacement candles
- **Market Structure upgrades** — CHoCH+ classification, structure bias, counter-trend FVG purge on CHoCH
- **Fibonacci OTE Zone (Section 14.9)** — 50–70.5% retracement zone
- **Setup Lifecycle (Section 16)** — pending → active with CE-touch close confirmation and a news gate
- Confluence score expanded to a max of 225 with grade-aware sweep/FVG weighting
- Dashboard grown to 25 rows; alerts for all FVG states and displacement

---

## [2.4.0] — 2026-08-10

### Added
- **Confluence Scoring Engine** — weighted score combining all detections
- RSI overbought/oversold and divergence contribution
- Volume spike contribution
- VWAP alignment contribution

---

## [2.3.0] — 2026-08-10

### Added
- **Market Structure Engine** — Break of Structure (BOS) and Change of Character (CHoCH) from confirmed pivots
- Structure bias state

### Fixed
- Dashboard / UI layout fixes

---

## [2.2.0] — 2026-08-10

### Added
- **FVG Engine** — fair value gap detection with an impulse-candle filter to suppress noise gaps

---

## [2.1.0] — 2026-08-08

### Added
- **Liquidity Engine** — complete BSL/SSL detection system
- Swing High/Low detection using `ta.pivothigh` / `ta.pivotlow` (confirmed pivots, no repaint)
- Buyside Liquidity (BSL) tracking — 5 levels max, FIFO eviction
- Sellside Liquidity (SSL) tracking — 5 levels max, FIFO eviction
- Equal High (EQH) classification — auto-upgrades when pivots land within tick tolerance
- Equal Low (EQL) classification — same logic for lows
- Sweep detection on `high[1]` / `close[1]` — previous bar confirmed close, zero repainting
- Swept level expiry — configurable bar count before swept levels are removed
- Event variables: `EVT_BSL_SWEPT`, `EVT_SSL_SWEPT`, `EVT_BSL_PRICE`, `EVT_SSL_PRICE`
- Dashboard rows: Liq Levels count, Last Sweep info
- Debug section: BSL/SSL active counts, last sweep, event states
- Alert: Buyside Liquidity Swept
- Alert: Sellside Liquidity Swept
- Sweep signal markers (triangle shapes on chart)

### Changed
- Visual rework: BSL/SSL lines now solid (width 2) instead of dotted
- Labels upgraded to `size.small` with icon prefixes (▼ BSL, ▲ SSL, ◆ EQH/EQL)
- BSL labels positioned above lines, SSL labels below lines
- EQH/EQL lines thicker (width 3) to visually distinguish from regular levels
- EMAs now 60% transparent — subtle background reference
- PDH/PDL now 70% transparent with step-line style
- Label pinning offset increased to `bar_index + 8` for breathing room
- `max_labels_count` increased to 50
- `max_lines_count` increased to 50

---

## [2.0.1] — 2026-08-07

### Added
- **Foundation Architecture** — clean rewrite from v2.0.0 prototype
- Constants module — all magic strings, colors, lengths centralized
- Input groups — EMA, PDH, HTF, Sessions, Dashboard, Debug with inline color pickers
- Helper functions: `fn_trend_color`, `fn_resolve_htf`, `fn_table_pos`, `fn_htf_label`
- Session Engine — India (09:15–15:30 IST), London, New York, Asia with UTC time windows
- HTF Engine — auto-mapping (1m→15m, 3m→30m, 5m→1H, 15m→4H, 30m→4H, 1H→Daily) + manual override
- Trend Engine — EMA 50/200 with Bullish, Bearish, Neutral states and change detection
- Context Engine — Previous Day High/Low via daily `request.security()`, Above/Below/Inside classification
- Visual Engine — EMA plots, PDH/PDL plots, all toggle-controlled
- Dashboard — `var table` (never recreated per bar), 8-row layout, updates only on `barstate.islast`
- Debug Engine — single `var label` reused every bar, full state dump
- Alert: Trend Change
- Alert: Session Change

### Notes
- Complete rewrite from v2.0.0 prototype due to architectural limitations
- All `request.security()` calls use `lookahead = barmerge.lookahead_off`
- Pine Script v6

---

## [2.0.0] — 2026-08-06

### Notes
- Initial prototype with swing detection, liquidity levels, FVG, entry logic, TP/SL boxes
- Testing revealed architectural limitations — decision made to rewrite from scratch
- Superseded by v2.0.1 foundation rewrite
