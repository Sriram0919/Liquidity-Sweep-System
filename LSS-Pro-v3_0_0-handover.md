# LSS Pro v3.0.0 — Handover Document

## 1. Current Objective
Build LSS Pro — a Pine Script v6 TradingView indicator for Smart Money Concepts (ICT) trading.
**Phase 3 (v3.0.0) is complete and compiled clean on MCX Crude Oil 5m (Aug 16 2026).**
Next milestone is **Phase 4** — see Section 6 below.

---

## 2. Completed Functionality

### Core Engines (all working)
| Section | Engine | Version |
|---------|--------|---------|
| 6 | HTF Structure Engine (real swing high/low bias, replaces EMA proxy) | v3.0.0 |
| 6B | HTF FVG & OB Engine (3-candle HTF FVG, OB body zone, CE proximity) | v3.0.0 |
| 11.5 | News Calendar (instrument-aware: EIA Crude / API Crude / EIA Nat Gas / manual) | v2.7.1 |
| 12 | Liquidity (BSL/SSL detection, sweep grading A/B/C, PDH/PDL bonus, inducement) | v2.7.0 |
| 12.5 | Displacement Detection (body%, range/ATR, volume/SMA → NONE/NORMAL/STRONG) | v2.7.0 |
| 13 | FVG Engine (5-state: Fresh→First Touch→CE Touch→Deep Retest→Mitigated) | v2.7.0 |
| 13B | Order Block Engine (border-only visuals, no fill) | v2.7.0 |
| 14 | Market Structure (BOS/CHoCH/CHoCH+, structure bias, counter-trend FVG purge) | v2.7.0 |
| 14.9 | Fibonacci OTE Zone (50–70.5% retracement, adaptive lookback, ▲/▼ label) | v2.7.1 |
| 15 | Confluence Scoring (max 260, HTF FVG/OB weights added) | v3.0.0 |
| 16 | Setup Lifecycle (pending→active, CE touch close confirmation, news gate) | v2.6.0 |
| 9 | Dashboard (27 rows, full HTF block at top) | v3.0.0 |
| 11 | Alerts (all events including FVG states and displacement) | v2.7.0 |

### Scoring Weights (max ~260)
| Factor | Points |
|--------|--------|
| Sweep A/B/C | 25/20/10 |
| Post-news sweep bonus | +15 |
| PDH/PDL sweep bonus | +15 |
| Inducement (double-sweep) | +10 |
| FVG CE Touch | 20 |
| FVG Fresh/First Touch | 15 |
| FVG Deep Retest | 5 |
| FVG post-sweep bonus | +10 |
| Structure BOS | +10 |
| Structure CHoCH | +20 |
| CHoCH+ bonus | +10 |
| Structure bias alignment | +10 |
| HTF structure bias alignment | +15 |
| HTF FVG active (price at CE) | +20 |
| HTF FVG active (not at CE) | +10 |
| HTF OB in zone | +15 |
| Kill Zone (London/NY/India) | +10 |
| Active session | +5 |
| PDH/PDL context | +5 |
| RSI OS/OB or divergence | +10 |
| Volume spike | +10 |
| VWAP alignment | +5 |
| OB proximity | +10 |
| OTE price in zone | +10 |
| OTE FVG CE in zone | +15 |
| Rejection candle | +10 |

---

## 3. Current Code State

- **File:** `LSS-Pro-v3_0_0.pine` (output from this session)
- **Repo:** `~/Documents/Liquidity-Sweep-System`, branch `develop`
- **Lines:** 3,741
- **Indicator title:** `"LSS Pro v3.0.0"`
- **VERSION constant:** `"v3.0.0"`
- **Compilation status:** Clean — compiled and visually verified on MCX Crude Oil 5m (Aug 16 2026)
- **Commit message:** `feat: Phase 3 HTF structure engine, HTF FVG/OB detection, scoring + dashboard (v3.0.0)`

---

## 4. Important Architecture Decisions

### Pine v6 Constraints (critical)
- **No `continue` in for loops** — use `if st != FVG_MITIGATED` wrapper instead
- **`var int` / `var float` can be assigned `na`** — only non-var typed declarations cannot
- **Functions cannot modify `var` globals** — pass values as return, use assignments outside functions
- **`hour()`/`minute()` don't accept timezone arg** — use `time("1", "HHMM-HHMM:D", "UTC")` session strings instead
- **`alertcondition` message must be const string** — no runtime string concatenation

### Data Flow (must preserve order)
```
ATR_VAL declared (above Section 6B — shared by 6B and Section 13)
→ Section 6 (HTF Structure: pivot highs/lows → HTF_BIAS, HTF_LAST_SH/SL)
→ Section 6B (HTF FVG + OB: 3-candle HTF pattern → HTF_FVG_*_ACTIVE, HTF_OB_*_NEAR)
→ Section 7 (Context: PDH/PDL)
→ Section 8 (Visual: EMA plots, PDH/PDL plots)
→ Section 4 (Session + KillZones)
→ Section 11.5 (News Calendar)
→ Section 12 (Liquidity)
→ Section 12.5 (Displacement)
→ Section 13 (FVG) [ATR_VAL already declared above — no redeclaration]
→ Section 13B (OB)
→ Section 14 (MS)
→ Section 14.8 (Counter-trend FVG purge)
→ Section 14.9 (OTE)
→ Section 15 (Scoring) [consumes HTF_BIAS, HTF_FVG_*, HTF_OB_* + all upstream]
→ Section 16 (Setup Lifecycle)
→ Section 9 (Dashboard — 27 rows)
```

### Key Design Decisions (v3.0.0 additions)
- **ATR_VAL moved to above Section 6B** — was in Section 13, caused CE10272 undeclared identifier error
- **HTF FVG visuals intentionally omitted** — HTF FVGs span 12+ LTF candles, boxes were confusing on 5m chart. All HTF context in dashboard rows 6–7 and scoring only
- **HTF_BIAS uses HTF_CLOSE vs last pivot** — `HTF_CLOSE > HTF_LAST_SH` = Bullish, `HTF_CLOSE < HTF_LAST_SL` = Bearish. Simple and non-repainting
- **HTF FVG tracks one zone per side** — most recent unmitigated bull/bear HTF FVG. Replaced when new one fires
- **TREND_STATE is now an alias for HTF_BIAS** — kept so alert condition and debug label compile without changes
- **Dashboard table rows bumped to 28** — was 26, caused "Row 26 out of bounds" error after adding HTF FVG/OB rows
- **Dashboard rows 1–27**: Session, News, HTF TF, HTF Bias, HTF SH/SL, HTF FVG, HTF OB, Context, PDH/PDL, Liq Levels, Last Sweep, FVG Active, FVG Quality, OB Active, Structure, Last Break, Score, OTE Zone, Signal, RSI, Trade, Direction, Entry, SL, TP1/TP2, R:R, Setup→Entry

### Carried-forward decisions (unchanged from v2.7.1)
- **`STRUCTURE_BIAS`** pre-declared in Section 12 pre-declarations
- **`EVT_DISP_BULL/BEAR`** pre-declared in Section 12
- **FVG states are strings** not ints — 50+ comparisons use string equality
- **`FVG_TESTED = "CE Touch"`** legacy alias for OB engine
- **FIFO arrays with reverse iteration** for removal
- **News engine uses `IS_CRUDE` / `IS_NATGAS` guards**
- **OTE lookback adaptive by TF** — mult 16/12/8/6
- **Signal diamonds have 3-bar cooldown**

---

## 5. Known Bugs / Pending Issues

### HTF Bias showing "—" on fresh load
- Expected on instruments with limited history or when HTF pivot hasn't fired yet
- HTF_BIAS shows "—" until `ta.pivothigh/pivotlow` returns a confirmed value on RESOLVED_HTF
- Not a bug — resolves after enough HTF bars have passed

### News Calendar — live verification pending
- Nifty/Bank Nifty during Wed 14:15–14:30 UTC still not confirmed clear in live session

### OTE Zone — bullish live test pending
- Math confirmed correct in v2.7.1, not yet seen on a live bull setup

---

## 6. Pending Milestones

### Phase 3 — COMPLETE ✓
- ~~Real HTF structure (swing high/low bias)~~ → done (v3.0.0)
- ~~HTF FVG detection~~ → done (v3.0.0)
- ~~HTF OB detection~~ → done (v3.0.0)
- ~~HTF scoring integration~~ → done (v3.0.0)
- ~~HTF dashboard section~~ → done (v3.0.0)

### Phase 4 — Backtesting & Signal Quality (NEXT)
Ideas to discuss and prioritise:
1. **Win-rate tracker** — log every closed trade (TP1/TP2/SL/BE) to a table, show win%, avg RR
2. **Score histogram** — track what scores setups actually had at entry vs outcome
3. **Setup replay mode** — step through past signals bar by bar
4. **Alert refinement** — fire alerts only above score threshold (e.g. ≥120), not on every signal
5. **My Ideas file** — check `My_ideas.rtf` in project for any features queued by the user

---

## 7. Exact Next Task

**Discuss Phase 4 priorities with the user.** Check `My_ideas.rtf` first — user may have queued features there.

**To verify state at start of new conversation:**
```bash
grep -n "string VERSION\|HTF_BIAS\|HTF_FVG_BULL_ACTIVE\|ATR_VAL" LSS-Pro-v3_0_0.pine | head -20
```
- `VERSION = "v3.0.0"`, `HTF_BIAS` found, `HTF_FVG_BULL_ACTIVE` found → Phase 3 complete → proceed to Phase 4
- `ATR_VAL` should appear only ONCE (above Section 6B, line ~532)

---

## 8. Files Needed

**Primary file:** `LSS-Pro-v3_0_0.pine`
- Repo: `~/Documents/Liquidity-Sweep-System`, branch `develop`

**No other files required.** Entire indicator is single-file.
