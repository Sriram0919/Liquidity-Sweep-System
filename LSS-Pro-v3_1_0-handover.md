# LSS Pro v3.1.0 — Handover Document

## 1. Current Objective
Build LSS Pro — a Pine Script v6 TradingView indicator for Smart Money Concepts (ICT) trading.
**Phase 4 (v3.1.0) is complete and compiled clean on MCX Crude Oil 5m.**
Next milestone is **Phase 5** — see Section 6 below.

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
| 15 | Confluence Scoring (rescaled 0–100, 23 components, tiered weights) | v3.1.0 |
| 16 | Setup Lifecycle (pending→active, CE touch close confirmation, news gate) | v2.6.0 |
| 17 | Win-Rate Tracker (TP2/TP1+BE/SL counters, Win%, Total R, Avg R, Expectancy, Avg Score) | v3.1.0 |
| 9 | Dashboard (28 rows, full HTF block at top) | v3.0.0 |
| 11 | Alerts (score-gated: ALT_SWEEP, ALT_CE, ALT_CHOCH bull/bear; pre-pos bull/bear) | v3.1.0 |

### Scoring Weights — v3.1.0 (0–100 scale, 23 components)
| Tier | Factor | Points |
|------|--------|--------|
| Core ICT (~50pts) | Sweep grade A/B/C | 9/7/4 |
| | FVG CE Touch | 7 |
| | FVG Fresh/First Touch | 3 |
| | Structure BOS | 4 |
| | Structure CHoCH | 7 |
| | CHoCH+ bonus | 4 |
| HTF Alignment (~25pts) | HTF structure bias | 6 |
| | HTF FVG active at CE | 7 |
| | HTF FVG active not at CE | 3 |
| | HTF OB in zone | 6 |
| | Session bias | 4 |
| Quality Markers (~15pts) | PDH/PDL sweep bonus | 5 |
| | Inducement (double-sweep) | 3 |
| | OTE in zone | 3 |
| | OTE FVG CE in zone | 5 |
| | Rejection candle | 4 |
| Supporting (~10pts) | Kill Zone | 2 |
| | RSI OS/OB or divergence | 3 |
| | Volume spike | 3 |
| | VWAP alignment | 2 |
| | OB proximity | 3 |
| | News post-sweep bonus | 5 |
| | Pre-positioning bonus | 8 |

---

## 3. Current Code State

- **File:** `LSS-Pro-v3_1_1.pine` (was `LSS-Pro-v3_1_0.pine` through v3.1.0)
- **Repo:** `~/Documents/Liquidity-Sweep-System`, branch `develop`
- **Indicator title:** `"LSS Pro v3.1.1"`
- **VERSION constant:** `"v3.1.1"`
- **Compilation status:** v3.1.0 compiled clean on MCX Crude Oil 5m. v3.1.1 edits are source-only — **recompile pending** (see Section 7).
- **Latest commit:** Wave 1 scoring-integrity fixes (Bugs A–D) — v3.1.1

---

## 4. Important Architecture Decisions

### Pine v6 Constraints (critical)
- **No `continue` in for loops** — use `if st != FVG_MITIGATED` wrapper instead
- **`var int` / `var float` can be assigned `na`** — only non-var typed declarations cannot
- **Functions cannot modify `var` globals** — pass values as return, use assignments outside functions
- **`hour()`/`minute()` don't accept timezone arg** — use `time("1", "HHMM-HHMM:D", "UTC")` session strings instead
- **`alertcondition` message must be const string** — no runtime string concatenation
- **Pine session day codes:** `1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday, 7=Saturday`

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
→ Section 17 (Win-Rate Tracker)
→ Section 9 (Dashboard — 28 rows)
```

### Key Design Decisions
- **ATR_VAL moved to above Section 6B** — was in Section 13, caused CE10272 undeclared identifier error
- **HTF FVG visuals intentionally omitted** — HTF FVGs span 12+ LTF candles, boxes were confusing on 5m chart. All HTF context in dashboard rows 6–7 and scoring only
- **HTF_BIAS uses HTF_CLOSE vs last pivot** — `HTF_CLOSE > HTF_LAST_SH` = Bullish, `HTF_CLOSE < HTF_LAST_SL` = Bearish. Simple and non-repainting
- **TREND_STATE is an alias for HTF_BIAS** — kept so alert condition and debug label compile without changes
- **Score rescaled to 0–100** — tiered weights, 23 components. Theoretical max may slightly exceed 100 (see Known Bugs); currently uncapped
- **Pre-positioning engine** — captures HTF bias in pre-news window, fires ALT_PREPOS_BULL/BEAR on post-news sweep confirmation with +8 score bonus
- **Score-gated alerts** — ALT_SWEEP, ALT_CE, ALT_CHOCH fire only when score ≥ `IN_ALERT_MIN_SCORE`
- **`fn_clear_trade_visuals()` called on TRADE_BE_HIT** — confirmed resolved inline in v3.1.0

### Carried-forward decisions (unchanged)
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

> **v3.1.1 (2026-08-28) — Wave 1 fixed Bugs A, B, C, D.** Code is now `LSS-Pro-v3_1_1.pine`.
> Remaining: Bugs E, F, G, H and the day-of-week verification (Wave 2).

### From external code review (Aug 2026)

#### ✅ FIXED in v3.1.1

**Bug A — HTF security indexing (Section 6B)** 🔴
`HTF_HIGH[2]` in the LTF chart context meant 2 *chart* bars back, not 2 HTF bars — on 5m/1H it landed on the same HTF candle, making the entire HTF FVG + HTF OB scoring (~13 pts) unreliable.
**Fix:** Section 4 now also pulls `HTF_{OPEN,HIGH,LOW,CLOSE}_1` and `_2` via `request.security(syminfo.tickerid, RESOLVED_HTF, [open[1], …], lookahead = barmerge.lookahead_off)`. Section 6B detection (`htf_fvg_bull_detected` etc.) and registration use those; `_2` = bar N-2, `_1` = N-1, bare = last closed HTF bar.

**Bug B — Score can exceed 100** 🔴
**Fix:** `conf_score = math.min(100, math.max(bull_score, bear_score))`. Deeper per-tier caps still deferred.

**Bug C — Dashboard score colour thresholds stale** 🟠
Bands were `101/81/61/41` (old ~285 scale). **Fix:** realigned to `70/55/40/25` to match the star thresholds.

**Bug D — Win-rate expectancy double-counts losses** 🟠
`wr_pct/100 * wr_avg_r - (1 - wr_pct/100)` — `wr_avg_r` is already net of losers.
**Fix:** dropped that formula. Added `WR_R_WINS` accumulator. Tracker row 7 **Expectancy** = `wr_avg_r` (net R/trade); row 8 repurposed to **Avg Win** = `WR_R_WINS / wr_wins`. TP1+BE realised R now `IN_TRADE_TP1_RR * 0.5` (was `TRADE_RR * 0.5`).

#### 🟠 OPEN — MEDIUM

**Bug E — Broken alert placeholder**
```pinescript
alertcondition(TREND_CHANGED, message = "... {{plot_0}} ...")
```
`{{plot_0}}` references a plotted series — `TREND_CHANGED` is not a plot. Message renders garbage. Fix: pass bias via a hidden `plot()`.

#### 🟡 MINOR

**Bug F — Closed-trade line objects leak**
On SL/TP, labels are deleted and line handles set to `na`, but `line.delete()` is never called on the 4 lines + 2 boxes. These accumulate toward `max_lines_count=150` and eventually new liquidity/FVG lines silently fail to draw.

**Bug G — Displacement computed twice**
Section 12 pre-declarations and Section 12.5 duplicate identical ATR/SMA/body math. Any threshold edit must be made in two places or sweep grading and FVG grading silently disagree.

**Bug H — RSI divergence logic is loose**
Bearish: `high[1] >= ta.highest(high, 10)[1]` is true most bars. Bullish uses different windows than price. This feeds ±3 points with essentially random polarity. Replace with proper pivot-based divergence or remove.

#### ℹ️ NOTES FROM REVIEW (verify before accepting)

**Day-of-week codes** — Reviewer claimed `:4` = Thursday and `:3` = Wednesday (suggesting EIA/API fire one day late). Per Pine's actual encoding (`1=Sun … 7=Sat`), `:4` = Wednesday and `:3` = Tuesday, which *matches* EIA Crude (Wed) and API Crude (Tue). **Reviewer appears to be wrong here — verify against live chart before changing.**

### Pre-existing known issues (carried forward)
- **HTF Bias showing "—" on fresh load** — expected until `ta.pivothigh/pivotlow` returns a confirmed value on RESOLVED_HTF. Not a bug.
- **News Calendar — live verification pending** — Nifty/Bank Nifty during Wed 14:15–14:30 UTC not yet confirmed clean in live session.
- **OTE Zone — bullish live test pending** — math confirmed correct in v2.7.1, not yet seen on a live bull setup.

---

## 6. Pending Milestones

### Phase 4 — COMPLETE ✓
- ~~Confluence score rescaled 0–100~~ → done (v3.1.0)
- ~~Win-rate tracker~~ → done (v3.1.0)
- ~~Score-gated alerts~~ → done (v3.1.0)
- ~~News pre-positioning engine~~ → done (v3.1.0)

### Phase 5 — Signal Quality & Visualization (NEXT)
Agreed capability gaps (from deep codebase review):
1. **Sweep-to-FVG distance filter** — reject setups where FVG is too far from sweep
2. **Entry candle quality gate** — require specific candle characteristics at entry
3. **Session-aware ATR SL multiplier** — different ATR multiples per session
4. **LTF+HTF FVG stack bonus scoring** — require LTF FVG to sit inside unmitigated HTF FVG
5. **Consecutive loss suppression guard** — pause signals after N losses within M bars
6. **Range/trend regime filter** — suppress signals in chop (ATR percentile < 20th) or chaos (> 95th)

Visualization gaps (agreed next build targets):
- **Weekly High/Low lines** — draw as chart lines (agreed immediate next task)
- **HTF swing level lines** — draw HTF_LAST_SH / HTF_LAST_SL as chart lines

Additional from external review (Tier 1 — high impact):
- **Premium/Discount equilibrium filter** — longs only below 50% of last impulse, shorts only above. Already have swings, trivial to add. High expected hit-rate improvement.
- **Volatility-regime gate** — ATR percentile filter (overlaps with gap #6 above)
- **Day-of-week / time-of-day filters** — avoid Friday afternoon, first 2 bars of illiquid opens

Deferred:
- Score histogram
- News countdown display
- TradingView plan limitations and phone alert workflows
- HTF alert conditions for FVG/OB events
- `strategy()` backtest twin
- Compact dashboard mode
- Single webhook-style JSON alert for bots
- SMT divergence (needs second-symbol input)

---

## 7. Exact Next Task

Wave 1 (Bugs A–D) is done in v3.1.1. Next:

1. **Wave 2 — Bugs E, F, G, H** + verify the day-of-week codes on a live chart (see Section 5).
2. **Wave 3 — Weekly High/Low chart lines**, then HTF swing level lines (`HTF_LAST_SH` / `HTF_LAST_SL`).
3. **Wave 4 — Phase 5 signal-quality filters** (premium/discount equilibrium first).

**To verify state at start of new conversation:**
```bash
grep -n "string VERSION\|HTF_HIGH_2\|Section 17\|WR_R_WINS\|ALT_PREPOS" LSS-Pro-v3_1_1.pine | head -20
```
- `VERSION = "v3.1.1"`, `HTF_HIGH_2` found, `WR_R_WINS` found → Wave 1 landed → proceed to Wave 2

---

## 8. Files Needed

**Primary file:** `LSS-Pro-v3_1_1.pine`
- Repo: `~/Documents/Liquidity-Sweep-System`, branch `develop`

**No other files required.** Entire indicator is single-file.
