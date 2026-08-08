# Changelog

All notable changes to LSS Pro are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/).

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
