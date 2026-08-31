"""PoC entrypoint.

    python -m bench.run_poc --csv data/mcx_crude_5m.csv
    python -m bench.run_poc --synthetic          # smoke test, no real data

Prints the baseline win % / expectancy / drawdown and the score
distribution (used to recalibrate the threshold vs the live indicator).
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from .config import Config
from .data import load_candles, synthetic_candles
from .engine import Engine
from .trade import run_trades, metrics


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="candle CSV (date,open,high,low,close,volume)")
    ap.add_argument("--synthetic", action="store_true", help="use random-walk data")
    ap.add_argument("--threshold", type=int, help="override conf_threshold")
    ap.add_argument("--entry-min", type=int, help="override entry_min_score")
    ap.add_argument("--mintick", type=float, help="instrument tick size")
    ap.add_argument("--volume-blind", action="store_true", help="force volume-blind mode")
    ap.add_argument("--pd-filter", action="store_true", help="Phase 5 #1 premium/discount gate")
    ap.add_argument("--dist-filter", type=float, help="Phase 5 #3 sweep->FVG distance ceiling (ATR)")
    ap.add_argument("--no-fill-strict", action="store_true", help="allow same-bar fill+exit (Pine-literal)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    if args.synthetic:
        df = synthetic_candles()
        src = "synthetic random-walk (NOT real metrics)"
    elif args.csv:
        df = load_candles(args.csv)
        src = args.csv
    else:
        ap.error("pass --csv PATH or --synthetic")

    cfg = Config()
    over = {}
    if args.threshold is not None:
        over["conf_threshold"] = args.threshold
    if args.entry_min is not None:
        over["entry_min_score"] = args.entry_min
    if args.mintick is not None:
        over["mintick"] = args.mintick
    if args.pd_filter:
        over["pd_filter"] = True
    if args.dist_filter is not None:
        over["dist_filter_atr"] = args.dist_filter
    if args.no_fill_strict:
        over["fill_strict"] = False
    # index spot has no real volume — auto-degrade the volume-based gates
    vol_blind = args.volume_blind or (not args.synthetic and float(df["volume"].fillna(0).abs().sum()) == 0.0)
    if vol_blind:
        over["volume_blind"] = True
        if args.mintick is None:
            over["mintick"] = 0.05          # NSE index tick
    if over:
        cfg = Config(**{**cfg.__dict__, **over})

    eng = Engine(df, cfg)
    views = eng.run()
    trades = run_trades(eng, views, cfg)
    m = metrics(trades)

    bull = np.array([s[0] for s in eng.scores])
    bear = np.array([s[1] for s in eng.scores])
    best = np.maximum(bull, bear)
    dist = {p: int(np.percentile(best, p)) for p in (50, 75, 90, 95, 99)}
    m["score_pctiles"] = dist
    m["score_max"] = int(best.max())
    m["bars"] = len(df)
    m["date_range"] = [str(df["date"].iloc[0]), str(df["date"].iloc[-1])]

    if args.json:
        print(json.dumps(m, indent=2))
        return

    print(f"\nLSS Pro backtest bench — PoC")
    print(f"source     : {src}")
    print(f"bars       : {m['bars']}   {m['date_range'][0]} .. {m['date_range'][1]}")
    print(f"threshold  : {cfg.conf_threshold}   (score pctiles {dist}, max {m['score_max']})")
    print("-" * 52)
    print(f"setups created      : {m['setups_created']}  (signal {m['from_signal']} / retest {m['from_retest']})")
    print(f"  expired/invalid   : {m['expired_or_invalid']}")
    print(f"closed trades       : {m['trades']}")
    print(f"  TP2 (full win)    : {m['tp2_full']}")
    print(f"  TP1+BE (partial)  : {m['tp1_be']}")
    print(f"  SL (loss)         : {m['sl']}")
    print("-" * 52)
    print(f"win %               : {m['win_pct']}")
    print(f"total R             : {m['total_r']:+}")
    print(f"expectancy (R/trade): {m['expectancy_r']:+}")
    print(f"avg win            : {m['avg_win_r']:+}R")
    print(f"max drawdown        : {m['max_dd_r']}R")
    print(f"avg entry score     : {m['avg_entry_score']} / 100")
    print()


if __name__ == "__main__":
    main()
