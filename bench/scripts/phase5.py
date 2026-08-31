"""Phase 5 filter experiment harness.

Two modes:
  * single CSV:  scripts/phase5.py data/banknifty_5m.csv --threshold 30 --entry-min 20
  * pooled:      scripts/phase5.py --pool            (globs data/pool/*.csv)

Pooled mode runs the full engine per instrument and concatenates the trades
so filter deltas are measured on a few-hundred-trade sample instead of ~30.
`data/pool/*.csv` = 2yr 1h NSE names from scripts/fetch_yf.py (real volume).

Prints one comparison table: baseline vs each signal-quality filter.
"""
from __future__ import annotations

import argparse
import glob
import pathlib

import numpy as np

from bench.config import Config
from bench.data import load_candles
from bench.engine import Engine
from bench.trade import run_trades, metrics

POOL = pathlib.Path(__file__).resolve().parent.parent / "data" / "pool"


def _agg(all_trades):
    m = metrics(all_trades)
    closed = [t for t in all_trades if t.outcome in ("tp2", "be", "sl")]
    # per-instrument spread of expectancy, to show it isn't one lucky symbol
    return m, closed


def run_variant(csvs, base_over, extra, tf1h):
    over = {**base_over, **extra}
    if tf1h:
        over.setdefault("ote_tf_mult", 8)
        over.setdefault("htf_period", "1D")
    all_trades = []
    for c in csvs:
        df = load_candles(c)
        o = dict(over)
        if float(df["volume"].fillna(0).abs().sum()) == 0.0:
            o["volume_blind"] = True
            o.setdefault("mintick", 0.05)
        cfg = Config(**{**Config().__dict__, **o})
        eng = Engine(df, cfg)
        views = eng.run()
        all_trades.extend(run_trades(eng, views, cfg))
    return metrics(all_trades)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--pool", action="store_true", help="glob data/pool/*.csv")
    ap.add_argument("--threshold", type=int, default=30)
    ap.add_argument("--entry-min", type=int, default=20)
    args = ap.parse_args(argv)

    if args.pool:
        csvs = sorted(glob.glob(str(POOL / "*.csv")))
        if not csvs:
            ap.error(f"no CSVs in {POOL} — run scripts/fetch_yf.py first")
        label = f"POOL ({len(csvs)} instruments, 1h/2yr)"
        tf1h = True
    else:
        if not args.csv:
            ap.error("pass a CSV path or --pool")
        csvs = [args.csv]
        label = args.csv
        tf1h = False

    base = {"conf_threshold": args.threshold, "entry_min_score": args.entry_min}

    variants = [
        ("baseline (fill-strict)",   {}),
        ("Pine-literal fill",        {"fill_strict": False}),
        ("#1 premium/discount",      {"pd_filter": True}),
        ("#3 dist<=1.5 ATR",         {"dist_filter_atr": 1.5}),
        ("#3 dist<=3 ATR",           {"dist_filter_atr": 3.0}),
        ("#1 + #3(3 ATR)",           {"pd_filter": True, "dist_filter_atr": 3.0}),
    ]

    hdr = (f"{'variant':<24} {'trades':>6} {'win%':>6} {'totR':>8} {'exp':>6} "
           f"{'DD':>6} {'setups':>7} {'exp/inv':>7}")
    print(f"\n{label}   threshold {args.threshold} / entry-min {args.entry_min}")
    print(hdr)
    print("-" * len(hdr))
    for name, extra in variants:
        m = run_variant(csvs, base, extra, tf1h)
        print(f"{name:<24} {m['trades']:>6} {m['win_pct']:>6} {m['total_r']:>+8.1f} "
              f"{m['expectancy_r']:>+6.2f} {m['max_dd_r']:>6.1f} {m['setups_created']:>7} "
              f"{m['expired_or_invalid']:>7}")
    print()


if __name__ == "__main__":
    main()
