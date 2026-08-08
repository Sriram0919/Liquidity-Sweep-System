# LSS Pro — Architecture

Technical reference for the engine design, data flow, and module responsibilities.

---

## System Overview

LSS Pro is a layered indicator where each engine operates independently but publishes events and state that downstream engines consume. No engine reaches into another engine's internals — communication happens through shared variables.

```
┌─────────────────────────────────────────────────┐
│                   INPUTS                         │
│  User-configurable settings per engine           │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│              LAYER 1: FOUNDATION                 │
│                                                  │
│  ┌──────────┐ ┌─────────┐ ┌───────┐ ┌────────┐ │
│  │ Session  │ │  HTF    │ │ Trend │ │Context │ │
│  │ Engine   │ │ Engine  │ │Engine │ │Engine  │ │
│  └────┬─────┘ └────┬────┘ └───┬───┘ └───┬────┘ │
│       │            │          │          │       │
│  Publishes:   Publishes:  Publishes: Publishes: │
│  ACTIVE_      RESOLVED_   TREND_     MARKET_    │
│  SESSION      HTF         STATE      CONTEXT    │
│  SES_*_       HTF_OHLC    TREND_     PD_HIGH    │
│  ACTIVE                   CHANGED    PD_LOW     │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│            LAYER 2: DETECTION                    │
│                                                  │
│  ┌──────────────┐ ┌──────────┐ ┌─────────────┐ │
│  │  Liquidity   │ │   FVG    │ │  Structure  │ │
│  │  Engine      │ │  Engine  │ │  Engine     │ │
│  │  (v2.1.0) ✓  │ │ (v2.2.0) │ │  (v2.3.0)  │ │
│  └──────┬───────┘ └────┬─────┘ └──────┬──────┘ │
│         │              │              │          │
│  Publishes:       Publishes:     Publishes:      │
│  EVT_BSL_SWEPT    EVT_FVG_BULL   EVT_BOS_BULL   │
│  EVT_SSL_SWEPT    EVT_FVG_BEAR   EVT_BOS_BEAR   │
│  EVT_BSL_PRICE    FVG arrays     EVT_CHOCH_BULL  │
│  EVT_SSL_PRICE                   EVT_CHOCH_BEAR  │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│          LAYER 3: INTELLIGENCE                   │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │       Confluence Scoring Engine          │    │
│  │              (v2.4.0)                    │    │
│  │                                          │    │
│  │  Reads all EVT_* variables              │    │
│  │  + TREND_STATE + MARKET_CONTEXT          │    │
│  │  + ACTIVE_SESSION                        │    │
│  │                                          │    │
│  │  Publishes: SCORE, SIGNAL_DIR, STARS     │    │
│  └────────────────────┬────────────────────┘    │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│            LAYER 4: OUTPUT                       │
│                                                  │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Trade Engine │  │      Dashboard           │ │
│  │  (v2.5.0)   │  │  (updated each version)  │ │
│  │              │  │                           │ │
│  │ Entry, SL,  │  │  Shows: score, stars,     │ │
│  │ TP1, TP2,   │  │  signal, R:R, confidence  │ │
│  │ R:R, conf%  │  │                           │ │
│  └──────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## Engine Details

### Session Engine (Section 4)

Determines which trading session is active based on UTC time windows.

| Session | UTC Window | IST Equivalent |
|---------|-----------|----------------|
| India | 03:45 – 10:00 | 09:15 – 15:30 |
| London | 08:00 – 16:30 | 13:30 – 22:00 |
| New York | 14:30 – 21:00 | 20:00 – 02:30 |
| Asia | 00:00 – 08:00 | 05:30 – 13:30 |

Priority order: India > London > New York > Asia. When sessions overlap, the highest-priority one is shown.

**Published state:** `ACTIVE_SESSION` (string), `ACTIVE_SESSION_COLOR` (color), `SES_*_ACTIVE` (booleans).

---

### HTF Engine (Section 5)

Maps the current chart timeframe to a higher timeframe for bias confirmation.

| Chart TF | HTF |
|----------|-----|
| 1m | 15m |
| 3m | 30m |
| 5m | 1H |
| 15m | 4H |
| 30m | 4H |
| 1H | Daily |

Uses a single `request.security()` call with tuple unpacking to fetch OHLC — minimizes security call overhead.

**Published state:** `RESOLVED_HTF` (string), `HTF_OPEN`, `HTF_HIGH`, `HTF_LOW`, `HTF_CLOSE` (floats).

---

### Trend Engine (Section 6)

Simple but effective: EMA 50 vs EMA 200.

- EMA50 > EMA200 → Bullish
- EMA50 < EMA200 → Bearish
- EMA50 == EMA200 → Neutral

**Published state:** `TREND_STATE` (string), `TREND_COLOR` (color), `TREND_CHANGED` (bool).

---

### Context Engine (Section 7)

Determines where price sits relative to the previous day's range.

- Close > PDH → "Above PDH" (bullish context)
- Close < PDL → "Below PDL" (bearish context)
- Between → "Inside Range" (neutral)

Uses `request.security()` with `high[1]` and `low[1]` on daily timeframe — fetches the *previous* day's levels, not the current day's developing levels.

**Published state:** `MARKET_CONTEXT` (string), `CONTEXT_COLOR` (color), `PD_HIGH`, `PD_LOW` (floats).

---

### Liquidity Engine (Section 12)

The first detection engine. Tracks where institutional stop orders are likely resting and detects when they get swept.

**Data structure:** 7 parallel arrays per side (BSL and SSL):

| Array | Type | Purpose |
|-------|------|---------|
| `*_price` | float | Price level of the pivot |
| `*_bar` | int | Bar index where pivot formed |
| `*_swept` | bool | Whether level has been swept |
| `*_swept_bar` | int | Bar index where sweep occurred |
| `*_type` | string | SH, EQH, SL, or EQL |
| `*_lines` | line | Visual line object |
| `*_labels` | label | Visual label object |

**Swing detection:** Uses `ta.pivothigh()` / `ta.pivotlow()` with configurable lookback. These functions return a value only when the pivot is confirmed (lookback bars have passed on both sides), guaranteeing zero repainting.

**EQH/EQL classification:** When a new pivot price falls within `IN_EQ_TOL * syminfo.mintick` of an existing unswept level, the existing level is upgraded to EQH/EQL with thicker line and different color. No duplicate level is added.

**Sweep detection:** Uses `high[1]` and `close[1]` (previous bar's confirmed data):

- BSL sweep: `high[1] > level AND close[1] < level` → bearish sweep (short setup)
- SSL sweep: `low[1] < level AND close[1] > level` → bullish sweep (long setup)

**Capacity:** 5 levels per side. When a 6th pivot is detected, the oldest level is removed (FIFO via `array.shift()`).

**Expiry:** Swept levels are removed after `IN_SWEPT_EXPIRY` bars. The expiry loop iterates backward (`n-1 to 0`) to safely remove elements mid-loop without index shifting.

**Published events:** `EVT_BSL_SWEPT` (bool), `EVT_SSL_SWEPT` (bool), `EVT_BSL_PRICE` (float), `EVT_SSL_PRICE` (float). These reset to `false` at the top of every bar and are set `true` only on the exact sweep confirmation bar.

---

## Performance Rules

1. **Reuse drawing objects** — all tables, labels use `var` declaration. Never create per bar.
2. **Dashboard updates only on `barstate.islast`** — zero cost on historical bars.
3. **Label position updates only on `barstate.islast`** — same principle.
4. **Minimize `request.security()` calls** — tuple unpacking fetches multiple values in one call.
5. **Array capacity limits** — 5 levels per side prevents unbounded growth.
6. **Backward iteration for removal** — prevents index shifting bugs in expiry loops.
7. **`extend.right` on active lines** — auto-extends without touching the line every bar.

---

## No-Repaint Guarantee

Every detection in LSS Pro uses confirmed data only:

| Engine | Method | Why It's Safe |
|--------|--------|---------------|
| Swing Detection | `ta.pivothigh(high, LB, LB)` | Returns value only after LB bars have confirmed on both sides |
| Sweep Detection | `high[1]`, `close[1]` | Uses previous bar's closed data, never current bar |
| HTF Data | `lookahead = barmerge.lookahead_off` | No future data leakage |
| Context (PDH/PDL) | `high[1]`, `low[1]` on daily | Previous day's levels, fully settled |

---

## Future Engine Contracts

### FVG Engine (v2.2.0)

Each FVG will store: price range (top/bottom), direction, width relative to ATR, age in bars, session it formed in, HTF alignment, mitigated status. FVGs below minimum ATR threshold will be filtered out.

**Will publish:** `EVT_FVG_BULL`, `EVT_FVG_BEAR`, FVG arrays for visual rendering.

### Structure Engine (v2.3.0)

Detects BOS (Break of Structure) and CHOCH (Change of Character) on both internal and external structure. Trend state will update based on structure breaks, not just EMA.

**Will publish:** `EVT_BOS_BULL`, `EVT_BOS_BEAR`, `EVT_CHOCH_BULL`, `EVT_CHOCH_BEAR`.

### Confluence Scoring Engine (v2.4.0)

Consumes all EVT_* variables plus foundation state. Calculates weighted score. Only generates trade setups when score exceeds configurable threshold.

**Will publish:** `SCORE` (int), `SIGNAL_DIR` (string), `STARS` (int 1-5).

### Trade Engine (v2.5.0)

Draws entry, stop loss, TP1, TP2 boxes. Calculates R:R ratio and confidence percentage. Only activates when Score Engine threshold is met.
