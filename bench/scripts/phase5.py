"""Entry-model + Phase-5 filter experiment harness.

    scripts/phase5.py --pool                       # 26-name 1h/2yr pool
    scripts/phase5.py --pool --dir pool5m --tf5m    # 10-name 5m/60d cross-check
    scripts/phase5.py data/banknifty_5m.csv        # single CSV

Pooled mode runs the full engine per instrument and concatenates the trades
so entry models / filters are measured on a few-hundred-trade sample.

Columns: trades = filled (tp2/be/sl/timeout); w/l/to = tp2+be / sl / timeout;
win% = share of positive-R trades; exp = R per filled trade.
"""
from __future__ import annotations

import argparse
import glob
import pathlib

from bench.config import Config
from bench.data import load_candles
from bench.engine import Engine
from bench.trade import run_trades, metrics

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


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
        all_trades.extend(run_trades(eng, eng.run(), cfg))
    return metrics(all_trades)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--pool", action="store_true")
    ap.add_argument("--dir", default="pool", help="pool subdir under data/ (default: pool)")
    ap.add_argument("--tf5m", action="store_true", help="pool is 5m data (keep 5m OTE/HTF tuning)")
    ap.add_argument("--threshold", type=int, default=30)
    ap.add_argument("--entry-min", type=int, default=20)
    args = ap.parse_args(argv)

    if args.pool:
        csvs = sorted(glob.glob(str(DATA / args.dir / "*.csv")))
        if not csvs:
            ap.error(f"no CSVs in {DATA / args.dir} — run scripts/fetch_yf.py first")
        tf = "5m" if args.tf5m else "1h"
        label = f"POOL {args.dir} ({len(csvs)} instruments, {tf})"
        tf1h = not args.tf5m
    else:
        if not args.csv:
            ap.error("pass a CSV path or --pool")
        csvs = [args.csv]
        label = args.csv
        tf1h = False

    base = {"conf_threshold": args.threshold, "entry_min_score": args.entry_min}

    M = {"entry_model": "market"}
    E = {"entry_model": "edge_limit"}
    variants = [
        ("ce_limit (Pine)",          {}),
        ("edge_limit",               E),
        ("market",                   M),
        ("market + #1 P/D",          {**M, "pd_filter": True}),
        ("market + #2 regime",       {**M, "regime_filter": True}),
        ("market + #3 dist3ATR",     {**M, "dist_filter_atr": 3.0}),
        ("market + #4 candle .5",    {**M, "candle_filter": 0.5}),
        ("market + #2 + #4",         {**M, "regime_filter": True, "candle_filter": 0.5}),
        ("edge_limit + #2 regime",   {**E, "regime_filter": True}),
        ("edge_limit + #4 candle .5", {**E, "candle_filter": 0.5}),
    ]

    hdr = (f"{'variant':<24} {'trades':>6} {'w/l/to':>10} {'win%':>6} {'totR':>8} "
           f"{'exp':>6} {'DD':>6} {'setups':>7}")
    print(f"\n{label}   threshold {args.threshold} / entry-min {args.entry_min}")
    print(hdr)
    print("-" * len(hdr))
    for name, extra in variants:
        m = run_variant(csvs, base, extra, tf1h)
        wl = f"{m['tp2_full'] + m['tp1_be']}/{m['sl']}/{m['timeout']}"
        print(f"{name:<24} {m['trades']:>6} {wl:>10} {m['win_pct']:>6} "
              f"{m['total_r']:>+8.1f} {m['expectancy_r']:>+6.2f} {m['max_dd_r']:>6.1f} "
              f"{m['setups_created']:>7}")
    print()


if __name__ == "__main__":
    main()
