# LSS Pro — Python Backtest Bench

Proof-of-concept port of the `LSS-Pro.pine` signal core to Python so the
Phase 5 signal-quality filters can be **measured** on historical data instead
of guessed. Pine stays the live/alert layer. See
[`../docs/Backtest-Bench-Plan.md`](../docs/Backtest-Bench-Plan.md).

## Status — Wave 5 (full engine port)

| Piece | State |
|---|---|
| Section 12 liquidity + sweep grading + PDH/PDL + inducement | ✅ |
| Section 12.5 displacement | ✅ |
| Section 13 FVG 5-state + post-sweep | ✅ |
| Section 13B LTF order blocks | ✅ `engine._spawn_ob` |
| Section 14 BOS / CHoCH / CHoCH+ + counter-trend purge | ✅ `market_structure.py` |
| Section 6 + 6B HTF structure + HTF FVG / OB | ✅ `htf.py` (5m→1H resample) |
| Section 14.9 Fibonacci OTE | ✅ `ote.py` |
| Section 15 confluence score — all 23 components | ✅ `scoring.py` (news/pre-pos stubbed) |
| Section 16 setup lifecycle + 16.7 retest + 16.8 exit model | ✅ `trade.py` |
| Section 17 metrics | ✅ |
| Section 11.5 news + pre-positioning | ⏳ stubbed (instrument-specific, ~13 pts) |
| First baseline on BankNifty 2yr | ✅ see `POC-FINDINGS.md` (needs threshold rescale) |

`structure.py` (swing-pivot proxy) is **superseded** by `market_structure.py`,
kept only for reference.

## Layout

```
bench/
  config.py      all IN_* tunables, mirrored from LSS-Pro.pine @ v3.2.0
  data.py        CSV load/write + synthetic smoke-test candles
  indicators.py  ATR/RSI (Wilder), SMA, VWAP, ta.pivothigh/low
  structure.py   swing-pivot proxy — SUPERSEDED by market_structure.py
  market_structure.py  Section 14 — BOS / CHoCH / CHoCH+ engine
  htf.py         Section 6 / 6B — HTF structure + HTF FVG / OB (1H resample)
  ote.py         Section 14.9 — Fibonacci OTE zone
  engine.py      bar-by-bar: displacement, liquidity, sweeps, FVG, OB, MS, HTF, OTE
  scoring.py     full 0–100 confluence score (23 components)
  trade.py       setup lifecycle + 16.7 retest + exit model + metrics
  run_poc.py     CLI entrypoint
scripts/
  fetch_kite.py  how to pull historical candles into data/
  phase5.py      filter experiment harness — baseline vs each Phase 5 filter
```

## Run

```bash
cd bench
python3 -m venv .venv && .venv/bin/pip install pandas numpy
.venv/bin/python -m bench.run_poc --synthetic              # pipeline smoke test
.venv/bin/python -m bench.run_poc --csv data/mcx_crude_5m.csv
```

`--synthetic` uses a random-walk generator (structureless — proves the
pipeline runs, **not** for real metrics).

### Phase 5 filter flags

```bash
.venv/bin/python -m bench.run_poc --csv data/banknifty_5m.csv --threshold 30 --entry-min 20 \
    --pd-filter --dist-filter 3.0            # #1 premium/discount + #3 sweep-distance
PYTHONPATH=. .venv/bin/python scripts/phase5.py data/banknifty_5m.csv --threshold 30 --entry-min 20
```

`--no-fill-strict` reverts to Pine-literal same-bar fill+exit. See
`POC-FINDINGS.md` Wave 5b for what the filters do to the numbers (short
version: BankNifty spot doesn't generate enough trades to rank them).

## Why a hand-rolled bar loop (not backtesting.py / vectorbt)

The PoC's job is to reproduce the Pine engine's numbers exactly so they're
comparable to the live Win-Rate Tracker. Pine's confirmed-bar `[1]`
semantics, same-bar SL priority, and TP1→BE→TP2 state machine translate
directly to an explicit loop. A framework is worth revisiting for step 5
(parameter sweeps over the Phase 5 filters).

## Known divergences from the live indicator

1. News (11.5) + pre-positioning stubbed to 0 (~13 pts).
2. Even with the full engine, components rarely co-occur → score p99 ≈ 36
   (BankNifty, volume-blind) / 38 (Crude). Rescale `conf_threshold` /
   `entry_min_score` ~0.55× from the `--json` `score_pctiles`.
3. `volume_blind` mode (auto for zero-volume CSVs): drops the sweep
   vol-factor, vol-spike (+3) and VWAP (+2); A/B sweep grades collapse to C.
4. Same-bar activation can let the entry candle's own `[1]` register a
   TP/SL — inflates win % / flattens drawdown. Fix pending.
5. HTF FVG/OB mitigation checked at LTF resolution (matches Pine 6B.4) but
   only 1 active zone per side is tracked (matches Pine).
