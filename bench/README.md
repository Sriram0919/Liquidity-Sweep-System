# LSS Pro — Python Backtest Bench

Proof-of-concept port of the `LSS-Pro.pine` signal core to Python so the
Phase 5 signal-quality filters can be **measured** on historical data instead
of guessed. Pine stays the live/alert layer. See
[`../docs/Backtest-Bench-Plan.md`](../docs/Backtest-Bench-Plan.md).

## Status — PoC (Wave 4)

| Piece | State |
|---|---|
| Project scaffold + bar-loop engine | ✅ |
| Section 12 liquidity: BSL/SSL levels, sweep detection + A/B/C grading, PDH/PDL, inducement | ✅ ported |
| Section 12.5 displacement | ✅ ported |
| Section 13 FVG 5-state machine + post-sweep tag | ✅ ported |
| Section 15 confluence scoring | ⚠️ **reduced-component** — see `scoring.py` docstring |
| Section 16 setup lifecycle + 16.8 TP1/TP2/BE/SL exit model | ✅ ported (confluence-signal setups only; retest pipeline not ported) |
| Section 17 metrics (win %, R, expectancy, drawdown) | ✅ |
| Section 6/6B HTF, 14 BOS/CHoCH, 14.9 OTE, 11.5 news, 13B order blocks | ❌ PoC out of scope (step 4 of the plan) |
| Real Kite MCX Crude 5m data | ⏳ pending Kite auth |
| Baseline metrics | ⏳ blocked on data |

`StructureBias` (`structure.py`) is a swing-pivot proxy for Section 14 —
a documented divergence.

## Layout

```
bench/
  config.py      all IN_* tunables, mirrored from LSS-Pro.pine @ v3.2.0
  data.py        CSV load/write + synthetic smoke-test candles
  indicators.py  ATR/RSI (Wilder), SMA, VWAP, ta.pivothigh/low
  structure.py   swing-pivot structure-bias proxy (PoC)
  engine.py      bar-by-bar: displacement, liquidity, sweeps, FVG state
  scoring.py     reduced 0–100 confluence score
  trade.py       setup lifecycle + exit model + metrics
  run_poc.py     CLI entrypoint
scripts/
  fetch_kite.py  how to pull historical candles into data/
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

## Why a hand-rolled bar loop (not backtesting.py / vectorbt)

The PoC's job is to reproduce the Pine engine's numbers exactly so they're
comparable to the live Win-Rate Tracker. Pine's confirmed-bar `[1]`
semantics, same-bar SL priority, and TP1→BE→TP2 state machine translate
directly to an explicit loop. A framework is worth revisiting for step 5
(parameter sweeps over the Phase 5 filters).

## Known divergences from the live indicator

1. Scoring omits ~45 pts of HTF / structure / OTE / news / OB components →
   PoC `best` scores top out well below 100; recalibrate `conf_threshold`
   from the `--json` `score_pctiles` before comparing win rates.
2. Only confluence-signal setups; the FVG-retest entry pipeline (Pine 16.7)
   is not ported → fewer trades than live.
3. `_best_fvg` = active FVG with CE nearest close; Pine's `fn_best_*_fvg`
   not yet read.
4. Structure bias is a swing proxy, not the BOS/CHoCH state machine.
