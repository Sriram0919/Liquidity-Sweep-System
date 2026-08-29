# PoC Findings — Wave 4 (2026-08-29)

Proof-of-concept Python port of the LSS Pro sweep + FVG + scoring core, run
on **real MCX Crude 5m data** (front-month `CRUDEOIL26SEPFUT`, token
144870151, **2026-06-01 → 2026-08-28, 7,623 candles ≈ 3 months**) pulled via
the Kite MCP.

## What works

The full pipeline runs end-to-end on real data:
displacement → liquidity levels → sweep detection + A/B/C grading → PDH/PDL →
inducement → FVG 5-state machine → reduced confluence score → setup
lifecycle → TP1/TP2/BE/SL exit model → R metrics.

Sweeps fire (~380 events / 3 mo on synthetic; comparable on real), FVGs form,
states advance, the swing-based structure proxy tracks bias.

## What the PoC revealed (the useful part)

### 1. The reduced-component score cannot be thresholded to match live

Ported ~55 of the ~100 scoring points. The unported ~45 pts (HTF bias +6,
HTF FVG +7/+4, HTF OB +6, BOS +4, CHoCH +7/+4, CHoCH+ +4, kill zone +4,
context +2, OTE +3/+5, news +5, pre-positioning +8, LTF OB +3) are **not
optional**: the PoC score ceiling on real data is **36** (99th pctile 24),
so the live `conf_threshold = 55` / `entry_min_score = 40` gates admit
**zero** trades. Absolute thresholds are not portable until Section 6/6B +
Section 14 are ported.

### 2. The confluence-signal entry path alone yields almost no trades

Even with proportionally lowered gates (threshold 18 / entry-min 12):
**97 setups created, 92 expired or invalidated, 5 activated** (all TP2, no
SL, no partials) over 3 months. Setups expire at exactly `setup_max_age`
(20 bars) — on 5m Crude, price rarely retraces to the FVG CE within 20 bars
of a confluence signal. Same-bar activation is essentially the only path
that fires.

**Implication:** the **FVG-retest pipeline (Pine Section 16.7)** — not ported
in the PoC — is likely where most live trades originate. It must be ported
before any baseline is meaningful.

### 3. Data availability

Kite MCP serves 5m candles for the front-month MCX future only back to
roughly its liquid period (~June for the SEP contract). `continuous=true`
fails through the MCP. A 2+ year sample needs either the kiteconnect SDK
with a continuous contract, or manual stitching of successive front-month
contracts across expiries. Each ~20-day pull is ~200–300 KB (saved to a
tool-results file, parsed offline — never fits in context).

## Verdict on "is the full engine port worth it?"

**Yes, but the PoC scope was too narrow to produce a baseline.** The port
translates cleanly (no Pine-semantics surprises — confirmed-bar offsets,
same-bar SL priority, RMA indicators all map directly). The blocker is that
"sweep + FVG + scoring core" as scoped omits the pieces that actually gate
and generate live trades. Revised step-4 scope:

- [ ] Port Section 14 (BOS / CHoCH / CHoCH+) — real structure bias
- [ ] Port Section 6 + 6B (HTF structure + HTF FVG/OB via resampled candles)
- [ ] Port Section 16.7 (FVG-retest entry pipeline)
- [ ] Port Section 14.9 (OTE) — cheap, arithmetic
- [ ] Then: full 0–100 score → live `conf_threshold=55` becomes comparable
- [ ] Get 2+ yr data (kiteconnect SDK, continuous contract)
- [ ] Produce the actual baseline win% / expectancy / max DD

News (11.5) and pre-positioning can stay stubbed for the first baseline
(instrument-specific, ~13 pts, only active around EIA/API windows).

## Data on hand (2026-08-29)

| file | instrument | span | bars | volume |
|---|---|---|---|---|
| `data/banknifty_5m.csv` | NSE:NIFTY BANK spot | 2024-06 → 2026-08 (487 days, Sep-2024 partial) | 36,399 | **0** (index spot) |
| `data/crude_5m.csv` | MCX CRUDEOIL26SEPFUT | 2026-06 → 2026-08 | 7,623 | real |

Decision (user, 2026-08-29): run the baseline on **BankNifty spot 2yr**,
volume-blind — most Phase 5 filters are price/structure based. Degrade the
displacement gate to body%+range only; vol-spike / VWAP / sweep-grade
factor-3 go neutral. Keep Crude as a fidelity cross-check. Pay for Kite
Connect later, only for a final Crude validation run.

Pulled via ~39 `mcp__Kite__get_historical_data` calls in ~18-day windows;
raw JSON in `bench/data/raw/` (git-ignored), stitched by
`scripts/stitch.py banknifty`.

## Reproduce

```bash
cd bench
.venv/bin/python -m bench.run_poc --csv data/banknifty_5m.csv --threshold 18 --entry-min 12
.venv/bin/python -m bench.run_poc --csv data/crude_5m.csv --json   # score distribution
```
