# LSS Pro — Liquidity Sweep System

A professional-grade TradingView indicator built on Smart Money Concepts (SMC) / ICT methodology.

LSS Pro is not just another liquidity sweep indicator — it's a complete institutional trading framework that detects liquidity sweeps, fair value gaps, market structure breaks, and scores trade setups by confluence before generating entries.

---

## Current Version: v2.1.0 — Liquidity Engine

### What's Live

**Foundation (v2.0.1)**
- Session Engine — India, London, New York, Asia with auto-detection
- HTF Engine — auto-maps chart timeframe to higher timeframe (1m→15m, 5m→1H, etc.) with manual override
- Trend Engine — EMA 50/200 with Bullish, Bearish, Neutral states
- Context Engine — Previous Day High/Low with Above/Below/Inside classification
- Dashboard — professional layout showing all engine states in real time
- Debug Framework — single reusable label with full engine state dump
- Alert Engine — trend change and session change alerts

**Liquidity Engine (v2.1.0)**
- Swing High/Low detection using confirmed pivots (zero repainting)
- Buyside Liquidity (BSL) — swing highs and equal highs where buy stops rest
- Sellside Liquidity (SSL) — swing lows and equal lows where sell stops rest
- EQH/EQL classification — pivots within configurable tick tolerance auto-upgrade
- Sweep detection on previous bar close — guaranteed no repaint
- Swept level expiry with configurable duration
- Event variables (EVT_BSL_SWEPT, EVT_SSL_SWEPT) for downstream engines
- BSL/SSL sweep alerts

---

## Roadmap

| Version | Module | Status |
|---------|--------|--------|
| v2.0.1 | Foundation | Done |
| v2.1.0 | Liquidity Engine | Done |
| v2.2.0 | FVG Engine | Planned |
| v2.3.0 | Market Structure (BOS/CHOCH) | Planned |
| v2.4.0 | Confluence Scoring Engine | Planned |
| v2.5.0 | Trade Management Engine | Planned |
| v3.0 | Institutional Suite | Future |

---

## How It Works

LSS Pro is built in layers. Each layer feeds the next:

```
Layer 1: Foundation
  Session → HTF → Trend → Context
                ↓
Layer 2: Detection
  Liquidity Engine → FVG Engine → Structure Engine
                ↓
Layer 3: Intelligence
  Confluence Scoring Engine (weighted score from all detections)
                ↓
Layer 4: Output
  Trade Engine (entry, SL, TP1, TP2, R:R, confidence %)
```

The Confluence Scoring Engine is the core differentiator. Instead of binary BUY/SELL signals, it calculates a weighted score:

| Factor | Weight |
|--------|--------|
| HTF Trend Alignment | +25 |
| Active Session | +10 |
| Liquidity Sweep | +30 |
| Fair Value Gap | +20 |
| Break of Structure | +15 |
| Premium/Discount Zone | +10 |

Trades only fire when the score exceeds a configurable threshold.

---

## Setup

1. Open TradingView → Pine Editor
2. Paste the contents of `src/LSS-Pro-v2.1.0.pine`
3. Click **Add to Chart**
4. Recommended: test on NIFTY 5m or BTCUSDT 5m

### Configurable Settings

- **Swing Lookback** — bars required on each side of a pivot (default: 5)
- **EQH/EQL Tolerance** — tick threshold for equal high/low classification (default: 3.0)
- **Show/Hide** — toggle BSL, SSL, EMAs, PDH/PDL, Dashboard, Debug independently
- **Colors** — fully customizable for BSL, SSL, EQH, EQL, swept levels
- **Swept Expiry** — how many bars before swept levels fade out (default: 30)
- **Dashboard Position** — top-left, top-right, bottom-left, bottom-right
- **HTF Mode** — auto-mapping or manual override

---

## Testing

**Primary:** NIFTY 5m (NSE)

**Secondary:** BANKNIFTY, FINNIFTY

**Additional:** BTCUSDT, ETHUSDT (for after-hours testing)

Use TradingView's **Bar Replay** to test on historical data when markets are closed.

---

## Design Principles

- **No repainting** — all detections use confirmed bars only
- **Modular architecture** — each engine is independent
- **Performance first** — reuse labels, tables, lines; minimize request.security() calls
- **No duplicated logic** — one responsibility per function
- **Professional variable names** — no magic numbers

---

## Repository Structure

```
Liquidity-Sweep-System/
  src/
    LSS-Pro-v2.1.0.pine
  docs/
    Architecture.md
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

---

## License

Private — All rights reserved.
