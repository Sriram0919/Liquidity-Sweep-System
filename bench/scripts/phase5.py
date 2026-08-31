"""Phase 5 filter experiment harness.

Runs the full engine on one CSV across a set of Config variants and prints a
comparison table so each signal-quality filter's delta vs the baseline is
visible in one place.

    cd bench && .venv/bin/python scripts/phase5.py data/banknifty_5m.csv --threshold 30 --entry-min 20
"""
from __future__ import annotations

import argparse

from bench.config import Config
from bench.data import load_candles
from bench.engine import Engine
from bench.trade import run_trades, metrics


def run(df, base_over, extra):
    cfg = Config(**{**Config().__dict__, **base_over, **extra})
    eng = Engine(df, cfg)
    views = eng.run()
    trades = run_trades(eng, views, cfg)
    return metrics(trades)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--threshold", type=int, default=30)
    ap.add_argument("--entry-min", type=int, default=20)
    args = ap.parse_args(argv)

    df = load_candles(args.csv)
    vol_blind = float(df["volume"].fillna(0).abs().sum()) == 0.0
    base = {"conf_threshold": args.threshold, "entry_min_score": args.entry_min}
    if vol_blind:
        base["volume_blind"] = True
        base["mintick"] = 0.05

    variants = [
        ("baseline (fill-strict)",     {}),
        ("Pine-literal fill",          {"fill_strict": False}),
        ("#1 premium/discount",        {"pd_filter": True}),
        ("#3 dist<=1.5 ATR",           {"dist_filter_atr": 1.5}),
        ("#3 dist<=3 ATR",             {"dist_filter_atr": 3.0}),
        ("#1 + #3(3 ATR)",             {"pd_filter": True, "dist_filter_atr": 3.0}),
    ]

    hdr = f"{'variant':<24} {'trades':>6} {'win%':>6} {'totR':>7} {'exp':>6} {'DD':>5} {'setups':>7} {'exp/inv':>7}"
    print(f"\n{args.csv}   threshold {args.threshold} / entry-min {args.entry_min}"
          f"   ({'volume-blind' if vol_blind else 'real volume'})")
    print(hdr)
    print("-" * len(hdr))
    for name, extra in variants:
        m = run(df, base, extra)
        print(f"{name:<24} {m['trades']:>6} {m['win_pct']:>6} {m['total_r']:>+7.1f} "
              f"{m['expectancy_r']:>+6.2f} {m['max_dd_r']:>5.1f} {m['setups_created']:>7} "
              f"{m['expired_or_invalid']:>7}")
    print()


if __name__ == "__main__":
    main()
