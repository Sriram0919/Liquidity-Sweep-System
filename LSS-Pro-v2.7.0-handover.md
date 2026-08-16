# LSS Pro v2.7.1 — Handover Document

## 1. Current Objective
Build LSS Pro — a Pine Script v6 TradingView indicator for Smart Money Concepts (ICT) trading.
**Phase 2 (v2.7.1) is complete and committed.**
Next milestone is **Phase 3 (v3.0.0)** — MTF Intelligence (real HTF structure driving LTF entries).

---

## 2. Completed Functionality

### Core Engines (all working)
| Section | Engine | Version |
|---------|--------|---------|
| 11.5 | News Calendar (instrument-aware: EIA Crude / API Crude / EIA Nat Gas / manual) | v2.7.1 |
| 12 | Liquidity (BSL/SSL detection, sweep grading A/B/C, PDH/PDL bonus, inducement) | v2.7.0 |
| 12.5 | Displacement Detection (body%, range/ATR, volume/SMA → NONE/NORMAL/STRONG) | v2.7.0 |
| 13 | FVG Engine (5-state: Fresh→First Touch→CE Touch→Deep Retest→Mitigated) | v2.7.0 |
| 13B | Order Block Engine (border-only visuals, no fill) | v2.7.0 |
| 14 | Market Structure (BOS/CHoCH/CHoCH+, structure bias, counter-trend FVG purge) | v2.7.0 |
| 14.9 | Fibonacci OTE Zone (50–70.5% retracement, adaptive lookback, ▲/▼ label) | v2.7.1 |
| 15 | Confluence Scoring (max 225, grade-aware sweep/FVG scoring, kill zones) | v2.7.0 |
| 16 | Setup Lifecycle (pending→active, CE touch close confirmation, news gate) | v2.6.0 |
| 9 | Dashboard (25 rows, News + OTE rows, FVG quality states, score /225) | v2.7.0 |
| 11 | Alerts (all events including FVG states and displacement) | v2.7.0 |

### Scoring Weights (max 225)
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
| HTF trend alignment | +15 |
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

- **File:** `LSS-Pro-v2.5.0.pine` (filename retained by convention, contains v2.7.1 code)
- **Repo:** `~/Documents/Liquidity-Sweep-System`, branch `develop`
- **Lines:** 3,485
- **Indicator title:** `"LSS Pro v2.7.1"`
- **VERSION constant:** `"v2.7.1"`
- **Compilation status:** Clean — compiled and visually verified on MCX Crude Oil 5m (Aug 16 2026)
- **Commit message:** `fix: instrument-aware news filter, adaptive OTE lookback, OTE bull verified (v2.7.1)`

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
Section 4 (Session+KillZones)
→ Section 11.5 (News Calendar) [uses IS_CRUDE/IS_NATGAS/IS_EQUITY + session time]
→ Section 12 (Liquidity) [declares EVT_BSL/SSL_SWEPT, STRUCTURE_BIAS pre-decl here]
→ Section 12.5 (Displacement) [declares EVT_DISP_BULL/BEAR, DISP_GRADE]
→ Section 13 (FVG) [uses STRUCTURE_BIAS, EVT_DISP_BULL/BEAR]
→ Section 13B (OB) [uses EVT_FVG_BULL/BEAR]
→ Section 14 (MS) [updates STRUCTURE_BIAS]
→ Section 14.8 (Counter-trend FVG purge) [uses EVT_CHOCH_BULL/BEAR]
→ Section 14.9 (OTE) [uses STRUCTURE_BIAS, fvg_bear/bull arrays, adaptive lookback]
→ Section 15 (Scoring) [consumes all upstream events]
→ Section 16 (Setup Lifecycle) [consumes EVT_SIGNAL_BULL/BEAR]
→ Section 9 (Dashboard)
```

### Key Design Decisions
- **`STRUCTURE_BIAS`** pre-declared in Section 12 pre-declarations (before FVG needs it in Section 13)
- **`EVT_DISP_BULL/BEAR`** pre-declared in Section 12 (before sweep grading which needs them, before Section 12.5 which formally computes them — no redeclaration in 12.5)
- **FVG states are strings** (`"Fresh"`, `"CE Touch"` etc.) not ints — 50+ comparisons across codebase use string equality
- **`FVG_TESTED = "CE Touch"`** legacy alias so OB engine works without changes
- **OB engine uses `FVG_FRESH` and `FVG_TESTED` for its own states** — these map to `"Fresh"` and `"CE Touch"` correctly
- **FIFO arrays with reverse iteration** for removal — always iterate `n-1 to 0` when removing
- **News engine uses `IS_CRUDE` / `IS_NATGAS` guards** before all `time()` session checks — non-crude/gas instruments see no auto events
- **OTE lookback is adaptive by TF** — `IN_MS_SWING_LB × _ote_tf_mult` where mult is 16/12/8/6 for ≤5m/≤30m/≤4H/daily+
- **OTE uses `ta.highestbars/ta.lowestbars`** to detect which came first (high or low) to determine swing direction
- **OTE box label shows ▲/▼** direction so traders immediately know which bias the zone applies to
- **Signal diamonds have 3-bar cooldown** and are filtered by structure direction

---

## 5. Known Bugs / Pending Issues

### News Calendar — Instrument Specificity
~~**Bug:** EIA and API crude oil events block setups on ALL instruments.~~
**FIXED in v2.7.1.** IS_CRUDE / IS_NATGAS / IS_EQUITY detection implemented.
Pending live verification: test on Nifty/Bank Nifty during Wed 14:15–14:30 UTC to confirm News stays "Clear".

### OTE Zone
- Bullish Fibonacci math verified and annotated in v2.7.1
- Adaptive lookback implemented — should now work correctly on 15m/1H/Daily
- ~~Not tested on bullish setups yet~~ — **math confirmed correct**, live test pending

### FVG Counter-trend Purge
- Purge fires on CHoCH only, not BOS — correct by design
- Old bullish FVGs formed well before structure flip may still appear briefly until CHoCH fires

---

## 6. Pending Milestones

### Phase 2 — COMPLETE ✓
- ~~News Calendar instrument filter~~ → done (v2.7.1)
- ~~Git commit v2.7.1~~ → done

### Phase 3 — v3.0.0 MTF Intelligence (NEXT)
1. Real HTF structure — HTF swing highs/lows using `request.security`, not EMA crossover
2. HTF FVG detection — bearish/bullish FVG zones on higher timeframe
3. HTF OB detection — order blocks on higher timeframe
4. LTF entry driven by HTF confluence — score weights HTF alignment heavily
5. HTF dashboard section showing HTF structure state

---

## 7. Exact Next Task

**Begin Phase 3 — Real HTF Structure Engine.**

Replace the current EMA 50/200 crossover proxy (`TREND_STATE`) with actual HTF swing high/low structure using `request.security`. The HTF is already resolved in Section 4 via `RESOLVED_HTF`.

### Architecture to build:

```pine
// Section 4 already has:
//   RESOLVED_HTF — auto or manual HTF string
//   [HTF_OPEN, HTF_HIGH, HTF_LOW, HTF_CLOSE] via request.security

// New: pull HTF pivot highs/lows
[htf_ph, htf_pl] = request.security(syminfo.tickerid, RESOLVED_HTF,
     [ta.pivothigh(high, 3, 3), ta.pivotlow(low, 3, 3)],
     lookahead = barmerge.lookahead_off)

// Track last confirmed HTF swing high and low
var float HTF_LAST_SH = na
var float HTF_LAST_SL = na

// HTF structure bias: BOS above last SH = bullish, below last SL = bearish
var string HTF_BIAS = MS_BIAS_NONE

// HTF FVG detection (3-candle pattern on HTF bars)
// HTF OB detection (last opposing candle before HTF displacement)
```

HTF bias then feeds directly into Section 15 scoring as the `HTF trend alignment +15` factor, replacing the current EMA crossover check.

### Dashboard addition:
Add HTF section rows below the existing Structure rows:
- HTF Bias (Bullish / Bearish / —)
- HTF Last SH / SL prices
- HTF FVG state (if any)

---

## 8. Files Needed

**Primary file:** `LSS-Pro-v2.5.0.pine` (filename retained by convention, contains v2.7.1 code)
- Repo: `~/Documents/Liquidity-Sweep-System`, branch `develop`

**No other files required.** The entire indicator is single-file.

**To verify state at start of new conversation:**
```bash
grep -n "string VERSION\|IS_CRUDE\|HTF_BIAS\|HTF_LAST_SH\|_ote_tf_mult" LSS-Pro-v2.5.0.pine | head -20
```
- `VERSION = "v2.7.1"` and `IS_CRUDE` found, `HTF_BIAS` NOT found → Phase 3 not yet started → begin Section 7 above
- `HTF_BIAS` found → Phase 3 in progress → read HTF section to find where it stopped
