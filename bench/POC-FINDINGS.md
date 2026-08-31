# Findings

## Wave 6 — self-review + entry-model comparison (2026-08-31)

Autonomous pass: audited the port against the Pine source, fixed what was
wrong, then attacked the real problem (the ~10 % fill rate) by testing
alternative entry models on two independent pools.

### Bugs fixed in the port

| bug | effect | fix |
|---|---|---|
| `_session_flags` hard-coded NSE hours (03:45–10:00 UTC) | on MCX Crude ~70 % of bars were flagged out-of-session, killing the retest path + session/KZ score | session bounds now derived from the feed's own daily time range (0.5/99.5 pctile) |
| HTF resample binned on wall-clock hours | NSE 1H bars are 09:15–10:15, not 09:00–10:00 → HTF FVG/OB/bias computed on misaligned bars | `origin="start"` for intraday HTF periods |
| `trade_max_age` silently dropped stalled trades | filled-but-going-nowhere trades vanished from P/L instead of booking a small result | mark-to-market at timeout (Wave 5c, verified here) |

Everything else audited (FVG 5-state, sweep grading, MS BOS/CHoCH, OTE
fib math, inducement, PDH/PDL, recent-event windows) matched Pine.

### Entry model is the lever — `market` and `edge_limit` both work

`scripts/phase5.py --pool` (26-name 1h/2yr) and `--pool --dir pool5m --tf5m`
(10-name 5m/60d). Threshold 30 / entry-min 20:

| model | 1h: trades / win% / exp / DD | 5m: trades / win% / exp / DD |
|---|---|---|
| **ce_limit** (Pine default) | 55 / 98 % / +1.75 / 1.0 | 36 / 94 % / +1.75 / 1.0 |
| **edge_limit** (near FVG edge) | 196 / 95 % / +1.38 / 1.0 | 136 / 90 % / +1.28 / 1.5 |
| **market** (open after signal) | 180 / 88 % / +1.24 / 3.0 | 115 / 85 % / +1.05 / 2.4 |

- **ce_limit's 98 % win rate is an artifact** — it only ever fills the ~10 %
  of setups where price retraced perfectly. **The live Pine indicator uses
  this model.**
- **`market` is the honest model** — ~all setups fill, DD is realistic
  (2.4–3 R), and the result is **still clearly positive: ~85–88 % win,
  +1.0–1.25 R expectancy** across both timeframes and 115–180 trades.
- Robust to threshold: market-entry expectancy holds +1.0–1.24 R from
  threshold 16 to 30 on both pools. It *drops* to +0.94 R at threshold 40 —
  **higher confluence score did not mean better trades.**
- **`edge_limit`** is the middle ground: more trades than ce_limit, higher
  win rate than market, DD still low — but retains mild selection bias
  (~40 % of setups still expire).

### Phase 5 filters — only #4 (entry-candle) shows anything

Tested against both entry models on both pools (threshold 22/15):

| filter | 1h market Δexp | 5m market Δexp | verdict |
|---|---|---|---|
| #1 premium/discount | +1.20→+1.07 | +1.04→+1.17 | noise, huge trade cut |
| #2 ATR-regime (skip pctile <20 / >95) | +1.20→+1.13 | +1.04→+1.04 | no help |
| #3 sweep-distance ≤3 ATR | +1.20→+1.10 | +1.04→+1.24 | noise, huge trade cut |
| **#4 signal-candle body ≥ 50 %** | **+1.20→+1.29, DD 2.0→1.0** | +1.04→+0.97 | **3 of 4 samples better; DD consistently halved** |

**Bottom line: no filter shows a robust edge.** #4 is the least bad — it
helps at some thresholds (22/15: +exp, DD 2.0→1.0) and is neutral at
others (30/20: slightly −exp). #1/#2/#3 are dead weight — big trade cuts,
no consistent payoff. If any filter is ported it should be #4, and only
after re-checking on the target instrument.

### The market-entry edge is broad, not one lucky instrument

`scripts/phase5.py --pool --breakdown market` (threshold 16/11, 1h/2yr):
**26 / 26 instruments net-positive expectancy**, 5–17 trades each,
per-instrument expectancy +0.5 to +1.85 R, win 62–100 %. The weakest
(POWERGRID, 62.5 % win) is still +0.69 R. 26 independent symbols all
positive is hard to explain by curve-fit or outlier.

### Remaining caveat

The 85–88 % win rate on `market` still carries intrabar optimism — with no
free 1-minute data we can't fully resolve "did SL or TP2 hit first" on a
wide bar. The 5m vs 1h agreement (85 % vs 88 %, +1.05 vs +1.24 R) bounds
the error at a few points, not tens. A tighter check needs 1m data.

### Recommendation

1. **Change the Pine indicator's entry model** — or add `market` /
   `edge_limit` as an input alongside the CE limit. The retrace-and-fill
   model misses ~90 % of the strategy's own signals.
2. **Drop Phase 5 filters #1, #2, #3.** Keep **#4 (signal-candle body ≥
   50 %)** — the only one that repeatably helps (small +exp, DD halved).
3. If porting `market` entry to Pine: it removes the pending-setup state
   machine entirely — simpler code.

---

## Wave 5c — free multi-instrument data + honest fill accounting (2026-08-31)

Can't pay for Kite Connect, so: **yfinance** (no auth) serves 60m candles
for ~2 years — anything sub-hour is capped at 60 days. Individual NSE
stocks carry **real volume**. `scripts/fetch_yf.py` pulls a 26-name basket
(24 liquid stocks + Nifty/BankNifty) into `data/pool/`; `scripts/phase5.py
--pool` runs the full engine per instrument and concatenates the trades.

Engine adds: `ote_tf_mult` config (16 for 5m, 8 for 1h) and mark-to-market
on `trade_max_age` (a filled trade that goes nowhere now books its real
small P/L instead of being silently dropped).

### Result 1 — real volume does NOT lift the score ceiling

26-name 1h pool, per-instrument p99 ≈ 37, pooled max 54 — same as
volume-blind BankNifty. **`conf_threshold=55` is unreachable on every
instrument and every timeframe tested.** The components just don't stack;
rescale stays ~0.55×.

### Result 2 — pooling helps, but the fill rate caps the sample at ~10 %

| pool, threshold 30/20 | value |
|---|---|
| setups created | 520 |
| **filled trades** | **55**  (10.6 % of setups) |
| win % | 98.2 |
| expectancy | +1.75 R |
| max DD | 1.0 R |

Threshold 20/14 → 658 setups, 69 fills (10.5 %), same shape. **~89 % of
confluence signals never see price return to the FVG CE within
`setup_max_age`.** That is the binding constraint — not the score gate,
not data length.

### Result 3 — the 98 % win rate is not trustworthy

It reflects, in unknown proportions: (a) a real "FVG holds in a
high-confluence retrace" edge, (b) heavy **selection bias** — only the
clean ~10 % of retracements ever fill, (c) **unresolvable intrabar
ordering** — with no free LTF data we can't tell whether a fill that later
reached TP first dipped through SL. `fill_strict` (skip the activation
bar) is optimistic; `--no-fill-strict` (SL-priority on the fill bar) is
pessimistic; the truth needs 1m data. Max DD pinned at 1.0 R across every
run = **variance is invisible at this trade count.**

### Result 4 — Phase 5 #1 and #3 do not show an edge

Two independent samples (BankNifty 5m n≈23, 26-name 1h pool n≈55):

| filter | trades | expectancy | verdict |
|---|---|---|---|
| baseline | 55 | +1.75 | — |
| #1 premium/discount | 17 | +1.38 | cuts fills 70 %, expectancy **down** |
| #3 sweep-dist ≤3 ATR | 11 | +1.59 | cuts fills 80 %, expectancy flat |
| #1 + #3 | 6 | +1.25 | worse |

The roadmap's premise ("premium/discount = highest expected hit-rate
gain, do first") is **not supported** by backtest. Both filters mainly
remove fills.

### Verdict — stop adding filters; fix the base metric

The measurable problems are (1) the ~10 % fill rate and (2) the
untrustworthy intrabar fill. Neither is solved by more filters or more
history. Next:
1. Test alternative entries — market-fill-on-signal vs CE-limit, FVG-edge
   vs CE — to see if fill rate can rise without collapsing the win rate.
2. Pull yfinance 5m/60d for ~10 names and spot-check how many "wins"
   would have stopped out intrabar.
3. Only then revisit the filters.

---

## Wave 5b — fill-model fix + first Phase 5 filter measurements (2026-08-31)

### Fix — same-bar fill+exit removed (`fill_strict`, default on)

A trade activated on bar `i` is now monitored only from bar `i+1`, so the
candle used to fill the entry (`bar[1]` at activation) can't also register
the exit. Impact on the 30/20 BankNifty baseline: 26→23 trades,
win 84.6→87.0 %, expectancy +1.14→+1.48 R, max DD unchanged (1.0 R).
Small — the look-ahead was not inflating results much — but it removes a
real bias. `--no-fill-strict` keeps the Pine-literal behaviour.

### The trade count is structurally capped (~34 on 2yr BankNifty)

Dropping `conf_threshold` from 30 to 14 takes setups from 273→419 but
closed trades only 23→37. Raising `setup_max_age` 20→160 *reduces* setups
(fewer slot turnovers) and leaves trades at ~32. **~90 % of setups expire
because price never retraces to the FVG CE.** This is not a parameter bug —
it is the confluence-signal→FVG-CE entry model's real signal frequency:
**≈11–18 trades/year on BankNifty 5m.**

### Phase 5 filters — implemented, but the sample is too thin to rank them

`scripts/phase5.py <csv> --threshold 30 --entry-min 20`

| variant | trades | win% | totR | exp | DD |
|---|---|---|---|---|---|
| baseline (fill-strict) | 23 | 87.0 | +34.0 | +1.48 | 1.0 |
| Pine-literal fill | 26 | 84.6 | +29.5 | +1.14 | 1.0 |
| #1 premium/discount | 7 | 71.4 | +8.0 | +1.14 | 1.0 |
| #3 sweep-dist ≤ 3 ATR | 5 | 100.0 | +10.0 | +2.00 | 0.0 |
| #1 + #3 | 1 | 100.0 | +2.0 | +2.00 | 0.0 |

- **#1 (longs in discount / shorts in premium)** cuts trades ~70 % and, on
  this sample, does **not** raise expectancy (+1.48→+1.14). n=7 — no
  conclusion, but it is not the obvious win the roadmap assumed.
- **#3 (post-sweep FVG within N ATR of the swept level)** as implemented is
  too strict — the `post_sweep` requirement alone leaves 3–5 setups in
  2 years. Needs a looser distance metric (bars sweep→FVG, or drop the
  post_sweep gate) before it can be measured.
- Max DD is pinned at exactly 1.0 R in every variant → never two losing
  trades in a row across the whole sample. With ~3 losses total that is
  plausible but unmeasurable — **variance is invisible at this trade count.**

### Verdict — the blocker is now data, not engine scope

The full engine is ported and honest. To rank the Phase 5 filters we need
**10–20× more trades**. Options, in order of value:
1. Kite Connect (paid) → 2+ yr Crude/Nifty **futures with real volume** —
   restores the +10 pts of volume-based score and lets `conf_threshold`
   run near its Pine default.
2. Add more instruments (NIFTY spot, large-cap stocks) to the bench and
   pool trades.
3. Accept ~15 trades/yr and forward-test the filters on the live Pine.

---

## Wave 5 — full engine port + first baseline (2026-08-29)

Ported the four remaining engines onto the bench:

| Pine section | bench module | notes |
|---|---|---|
| 14 — BOS / CHoCH / CHoCH+ | `market_structure.py` | replaces the `structure.py` swing proxy; real `STRUCTURE_BIAS`, counter-trend FVG purge on CHoCH wired into `engine.py` |
| 6 + 6B — HTF structure + HTF FVG/OB | `htf.py` | 5m→1H resample (`fn_resolve_htf`), HTF pivots 3/3, 1 active HTF FVG/OB per side, state updated at LTF resolution as in Pine 6B.4 |
| 14.9 — Fibonacci OTE | `ote.py` | rolling highest/lowest + `ta.highestbars` offsets, 50/61.8/70.5 % |
| 16.7 — FVG-retest entry pipeline | `trade.py` | same qualification gate as the confluence signal; `entered_zone = low[1]≤top ∧ close[1]≥bot ∧ low[2]>top` |
| 13B — LTF order blocks | `engine.py` `_spawn_ob` | needed for the +3 OB-proximity score |
| 15 — confluence score | `scoring.py` | **all 23 components** now ported (was ~12). News +5 / pre-pos +8 still stubbed. |

### Result 1 — the full-engine score still tops out ~50 on index spot

`banknifty_5m.csv` (volume-blind): score **max 50, p99 36, p90 28**.
`crude_5m.csv` (real volume): max 55, p99 38.

Even with every price/structure component ported, the live gates
(`conf_threshold=55`, `entry_min_score=40`) are essentially unreachable —
the components rarely co-occur on one bar, and volume-blind mode gives up
the sweep vol-factor (A/B→C), vol-spike (+3) and VWAP (+2). **Absolute
thresholds are not portable; they must be rescaled from the score
distribution.** Rescale factor ≈ 0.55 (55→30, 40→20).

### Result 2 — first baseline, BankNifty 2yr, rescaled 30 / 20

```
.venv/bin/python -m bench.run_poc --csv data/banknifty_5m.csv --threshold 30 --entry-min 20
```

| metric | value |
|---|---|
| closed trades | 26  (over 26 months ≈ 1/month) |
| win % | 84.6  (TP2 15 / TP1+BE 7 / SL 4) |
| total R | +29.5 |
| expectancy | +1.14 R / trade |
| max drawdown | 1.0 R |
| setups created | 276 (signal 248 / retest 28) — **250 expired or invalidated** |

### Result 3 — the churn is the signal-quality problem

~90 % of setups expire at `setup_max_age` (20 bars) without price
retracing to the FVG CE. The confluence-signal path fires far from usable
FVGs and holds the single trade slot, starving the retest path (28 of 276).
This is exactly what the Phase 5 filters target — **premium/discount
equilibrium** and **sweep-to-FVG distance** should cut the expiring
setups; measure each against this 30/20 baseline.

### Caveats

- 26 trades is too few for the win % to be trustworthy; treat as a smoke
  test of the pipeline, not a validated edge.
- Max DD 1.0R is suspiciously smooth — partly the same-bar-activation bias
  (entry candle's own `[1]` can register TP) noted in Wave 4. A fill model
  that requires activation strictly after the signal bar is the next
  fidelity step.
- News (11.5) + pre-positioning still stubbed (~13 pts, instrument-specific).

### Reproduce

```bash
cd bench
.venv/bin/python -m bench.run_poc --csv data/banknifty_5m.csv --threshold 30 --entry-min 20
.venv/bin/python -m bench.run_poc --csv data/banknifty_5m.csv --json   # score distribution
.venv/bin/python -m bench.run_poc --csv data/crude_5m.csv --threshold 30 --entry-min 20  # fidelity x-check
```

---

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
