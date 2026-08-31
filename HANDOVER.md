# LSS Pro — Handover Document

_Living doc — updated each wave. Current as of v3.2.0 (2026-08-29)._

## 1. Current Objective
Build LSS Pro — a Pine Script v6 TradingView indicator for Smart Money Concepts (ICT) trading.
**Phase 4 complete (v3.1.0). External-review backlog A–H closed (v3.1.1–v3.1.2).**
**Phase 5 started: v3.2.0 shipped weekly H/L + HTF swing-level lines.**
Next: Phase 5 signal-quality filters — see Section 6/7.

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

- **File:** `LSS-Pro.pine` — **frozen filename**. Version = `VERSION` constant + git tag, never the filename.
- **Repo:** `~/Documents/Liquidity-Sweep-System`, branch `develop`
- **Indicator title / VERSION:** `"v3.2.0"`
- **Compilation status:** v3.1.2 compiled clean on MCX Crude Oil 5m. v3.2.0 (Wave 3) edits are source-only — **recompile pending** (see Section 7).
- **Tags:** `v3.1.0`, `v3.1.1`, `v3.1.2` on `main`. v3.2.0 committed to `develop`, tag pending compile check.

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

> **v3.1.1 — Wave 1 fixed Bugs A–D. v3.1.2 — Wave 2 fixed Bugs E–H** (day-of-week codes verified correct).
> **Entire external-review backlog is closed.**
> **v3.2.0 — Wave 3** added weekly H/L + HTF swing lines. Next: Phase 5 signal-quality filters.

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

#### ✅ FIXED in v3.1.2

**Bug E — Broken trend alert placeholder** 🟠
`alertcondition(TREND_CHANGED, message = "... {{plot_0}} ...")` — `{{plot_0}}` had no matching plot.
**Fix:** split into two const-message conditions gated on `HTF_BIAS == HTF_BIAS_BULL` / `_BEAR` → "HTF Trend flipped Bullish / Bearish".

**Bug F — Closed-trade line/box leak** 🟡
On SL/TP2 close the code `label.delete()`d the labels then set `line`/`box` handles to `na` without deleting them → 4 lines + 2 boxes orphaned per trade.
**Fix:** stop nulling the line/box handles at close; the next setup's `fn_clear_trade_visuals()` now deletes them. At most one closed trade's visuals linger.

**Bug G — Displacement computed twice** 🟡
**Fix:** `DISP_ATR`, `DISP_VOL_SMA`, `disp_body`, `disp_range`, `disp_body_pct`, `disp_range_atr`, `disp_vol_ratio`, `disp_body_ok`, `disp_range_ok`, `disp_vol_ok`, `disp_all_ok` all declared once in Section 12's pre-declaration block; Section 12.5 reuses them and only adds the STRONG tier + `DISP_GRADE` / `DISP_DIR`.

**Bug H — RSI divergence logic loose** 🟡
Old comparison used a rolling 10-bar extreme that included the current bar → both conditions true on most bars.
**Fix:** pivot-to-pivot. Confirm a `ta.pivotlow(low, 5, 5)` / `pivothigh`, sample `CONF_RSI[5]` at that pivot bar, compare price + RSI to the previous confirmed pivot. `rsi_bull_div` = price LL + RSI HL; `rsi_bear_div` = price HH + RSI LH.

#### ✅ VERIFIED — no change (v3.1.2)

**Day-of-week codes** — Reviewer claimed `:4`/`:3` fire a day late. Pine session strings encode `1=Sun … 7=Sat`, so `:4`=Wed (EIA Crude), `:3`=Tue (API Crude), `:5`=Thu (EIA Nat Gas) — all correct, matching the comments. **Reviewer was wrong.** Live confirmation on a Wednesday crude session is still a nice-to-have.

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

### Phase 5 — Signal Quality & Visualization

Visualization — DONE (v3.2.0):
- ~~Weekly High/Low lines~~ → PW_HIGH / PW_LOW, group "Weekly Levels" (line objects, not plots — 64-plot cap)
- ~~HTF swing level lines~~ → HTF_LAST_SH / HTF_LAST_SL, group "HTF Swing Lines"

> **Before implementing the signal-quality filters below:** decision on 2026-08-29
> to first build a **Python backtest bench** so each filter can be measured, not
> guessed. Pine stays as the live layer. See `docs/Backtest-Bench-Plan.md`.
> Next concrete step there = a proof-of-concept port (sweep + FVG + scoring core)
> run on ~6 months of Kite Crude 5m data.

Signal-quality filters — to validate in the backtest bench, then port back (priority order):
1. **Premium/Discount equilibrium filter** — longs only below 50% of last impulse, shorts only above. Swings already exist (HTF_LAST_SH/SL + MS pivots). Highest expected hit-rate gain. **Do first.**
2. **Range/trend regime filter** — suppress signals when ATR percentile < ~20th (chop) or > ~95th (chaos)
3. **Sweep-to-FVG distance filter** — reject setups where the FVG is too far from the sweep
4. **Entry candle quality gate** — require specific candle characteristics at entry
5. **Session-aware ATR SL multiplier** — different ATR multiples per session
6. **LTF+HTF FVG stack bonus** — extra score when the LTF FVG sits inside an unmitigated HTF FVG
7. **Consecutive-loss suppression guard** — pause signals after N losses within M bars
8. **Day-of-week / time-of-day filter** — avoid Friday PM, first 2 bars of illiquid opens

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

Bug waves (A–H) done. Wave 3 (visualization) done in v3.2.0.
The Pine indicator is in a stable, releasable state.

**Next: NOT more Pine features.** Build the Python backtest bench —
see `docs/Backtest-Bench-Plan.md`.

**Wave 4 (2026-08-29) — PoC DONE.** `bench/` holds the Python port of
displacement + liquidity/sweep + FVG 5-state + reduced scoring + setup
lifecycle + TP1/TP2/BE/SL exit model + metrics. Full findings:
`bench/POC-FINDINGS.md`.

Key result: the port translates cleanly, but "sweep + FVG + scoring core"
was too narrow — reduced score caps ~29–36/100 (live threshold 55 admits
nothing) and the confluence-signal-only entry path fires ~5 trades over the
whole sample.

**Data — IN HAND** (`bench/data/`, git-committed CSVs):
- `banknifty_5m.csv` — NIFTY BANK spot, 2024-06 → 2026-08, 36,399 bars.
  **Baseline instrument** (user decision 2026-08-29). Volume-blind (index
  spot) — degrade displacement gate to body%+range, neutralise vol-spike /
  VWAP / sweep-grade factor-3. Most Phase 5 filters are price-based, so OK.
- `crude_5m.csv` — MCX SEP future, 2026-06 → 2026-08, 7,623 bars, real
  volume. Fidelity cross-check only (too short for stats).
- Kite MCP can't do better (`bench/scripts/fetch_kite.py`, [[kite-mcp-historical-limits]]);
  pay for Kite Connect later, only for a final Crude validation before Pine.

**Wave 5 (2026-08-29) — full engine port DONE.** Ported Section 14
(BOS/CHoCH/CHoCH+ → `bench/bench/market_structure.py`), Section 6+6B
(HTF → `bench/bench/htf.py`, 5m→1H resample), Section 14.9 (OTE →
`bench/bench/ote.py`), Section 16.7 (FVG-retest pipeline → `trade.py`),
Section 13B (LTF OBs) and the full 23-component score (`scoring.py`).
`structure.py` swing-proxy is superseded. Full findings:
`bench/POC-FINDINGS.md`.

Key results:
- Full-engine score still tops out ~50 (p99 36) on volume-blind BankNifty;
  ~55 on Crude. Live `conf_threshold=55` / `entry_min_score=40` are
  unreachable — **rescale ~0.55× from the score distribution** (55→30, 40→20).
- **First baseline, BankNifty 2yr, rescaled 30/20:** 26 closed trades,
  84.6% win, +29.5R, expectancy +1.14R, max DD 1.0R. BUT 250/276 setups
  expire before CE retrace, and 26 trades is too few to trust the win %.
- The expiring-setup churn IS the signal-quality gap — the Phase 5
  premium/discount + sweep-to-FVG-distance filters target exactly it.

**Wave 5b (2026-08-31) — fill-model fix + first Phase 5 measurements DONE.**
- `fill_strict` (default): trade monitored only from the bar AFTER
  activation — removes same-candle fill+exit. Baseline 30/20 now 23 trades,
  87% win, +34R, exp +1.48R.
- Filters #1 (premium/discount) and #3 (sweep→FVG distance) implemented
  (`Config.pd_filter`, `Config.dist_filter_atr`; harness `scripts/phase5.py`).
- **Result: sample too thin to rank filters.** Trade count is structurally
  capped ~34 on 2yr BankNifty (≈90% of setups expire before CE retrace,
  regardless of threshold or setup_max_age). #1 cuts trades ~70% and does
  NOT raise expectancy on n=7. #3 as written is too strict (post_sweep
  gate → 3–5 setups/2yr). Max DD pinned at 1.0R everywhere = variance
  invisible.

**Wave 5c (2026-08-31) — free data path + honest fill accounting DONE.**
- No paid data: `scripts/fetch_yf.py` pulls a 26-name NSE basket (yfinance,
  60m/2yr, real stock volume) → `data/pool/` (git-ignored, re-fetch free).
  `scripts/phase5.py --pool` runs the engine per instrument + concatenates.
- Engine: `ote_tf_mult` config (16=5m / 8=1h); mark-to-market on trade_max_age.
- **Findings (POC-FINDINGS Wave 5c):**
  - Real volume does NOT lift the score ceiling — p99 ≈ 37 on every
    instrument/TF. `conf_threshold=55` stays unreachable. Rescale ~0.55×.
  - Pooling → only ~55–70 *filled* trades: **~89% of confluence signals
    never see price retrace to the FVG CE** (fill rate ~10%). That, not
    the score gate or data length, is the binding constraint.
  - 98% win / +1.75R expectancy on fills is **not trustworthy** — selection
    bias + unresolvable intrabar SL-vs-TP (no free 1m data). Max DD pinned
    1.0R everywhere = variance invisible.
  - **Phase 5 #1 and #3 show NO edge** across two samples — both just
    remove fills, expectancy flat-to-down. Roadmap premise not supported.

**Wave 6 (2026-08-31, autonomous) — self-review + entry-model comparison DONE.**
- Fixed 3 port bugs: `_session_flags` hard-coded NSE hours (broke Crude
  retest path — now data-driven); HTF resample binned on wall-clock hours
  not session-aligned (`origin="start"`); trade timeout now marks-to-market.
  Rest of the port audited clean against Pine.
- Added `Config.entry_model` = `ce_limit` (Pine default) / `edge_limit` /
  `market`. Tested on 26-name 1h/2yr pool + 10-name 5m/60d pool.
- **RESULT — entry model is the lever:**
  - `ce_limit` (what live Pine uses): only ~10% of setups fill → its 98%
    win rate is an artifact of selection bias.
  - **`market` (enter at open on the signal): ~all fill, DD realistic
    (2.4–3R), still positive — 85–88% win, +1.0–1.25R expectancy across
    both timeframes, 115–180 trades. Robust threshold 16–30.**
  - `edge_limit`: middle ground (more trades than ce_limit, ~90–95% win).
  - Higher confluence score ≠ better trades (expectancy DROPS at threshold 40).
- **Phase 5 filters: none show a robust edge.** #1/#2/#3 = dead weight.
  #4 (signal-candle body ≥ 50%, `Config.candle_filter`) helps at some
  thresholds, neutral at others — the only one worth re-checking later.

**Concrete next step:**
1. **Port `market` (or `edge_limit`) entry to `LSS-Pro.pine`** — add as an
   input alongside the CE limit. This is the highest-value change: the
   retrace-fill model misses ~90% of the indicator's own signals. `market`
   also removes the pending-setup state machine (simpler Pine).
2. Get 1m data (still free-source only — investigate) to bound the residual
   intrabar optimism in the 85% win rate.
3. Roadmap filters: skip #1/#2/#3. Re-check #4 on the target instrument
   before bothering. Then try exit-model tweaks (trailing stop, time-stop)
   instead of more entry filters.
- News (11.5) + pre-positioning stay stubbed.

**To verify Pine state at start of a new conversation:**
```bash
grep -n "string VERSION\|PW_HIGH\|IN_SHOW_HTF_SWINGS\|fn_level_line" LSS-Pro.pine | head -20
```
- `VERSION = "v3.2.0"`, `PW_HIGH` + `fn_level_line` found → v3.2.0 confirmed

---

## 8. Files

- **Pine indicator:** `LSS-Pro.pine` (frozen name) — single file, the live/alert layer.
- **Backtest bench:** `bench/` — Python PoC (Wave 4). Entry: `bench/bench/run_poc.py`.
  Plan: `docs/Backtest-Bench-Plan.md`. Findings: `bench/POC-FINDINGS.md`.
  `bench/.venv` + `bench/data/*.csv` are git-ignored.
- Repo: `~/Documents/Liquidity-Sweep-System`, branch `develop`.
