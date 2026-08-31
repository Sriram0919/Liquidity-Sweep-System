"""Setup lifecycle + exit model — port of Pine Section 15.4/15.5 + 16 + 17.

Now includes the FVG-retest entry pipeline (Section 16.7) in addition to the
confluence-signal path (16.5). Single-slot state machine, matching Pine's
per-bar section order: 16.5 create → 16.6 pending monitor → 16.7 retest →
16.8 trade monitor (SL/TP/BE/expiry).

Exit model (16.8) unchanged:
  * monitoring on confirmed bar[1]
  * same-bar SL/TP -> SL priority
  * TP1 from ACTIVE -> SL to breakeven
  * BE after TP1 -> partial win R = tp1_rr * 0.5
  * TP2 -> full win R = tp2_rr ;  SL -> loss R = -1.0
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import (Engine, BULL, BEAR, NONE, FRESH, FIRST_TOUCH, CE_TOUCH,
                     DEEP_RETEST, MITIGATED)
from .scoring import score_bar

PENDING, ACTIVE, TP1_HIT = "pending", "active", "tp1_hit"


@dataclass
class Trade:
    dir: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    risk: float
    created_bar: int
    setup_score: int
    fvg_bot: float
    fvg_top: float
    fvg_ref: object = None
    source: str = "signal"          # "signal" | "retest"
    state: str = PENDING
    activate_bar: int = -1
    entry_score: int = 0
    exit_bar: int = -1
    outcome: str = ""
    r: float = 0.0


def _best_fvg(fvgs, close):
    """Pine fn_best_*_fvg — nearest CE (|close[1]-ce|) among non-mitigated,
    non-deep-retest FVGs."""
    cands = [f for f in fvgs if f.state not in (MITIGATED, DEEP_RETEST)]
    if not cands:
        return None
    return min(cands, key=lambda f: abs(f.ce - close))


def _find_sl(v, atrv, direction, entry, fvg_bound, buf):
    """Port of fn_find_sl_bull / fn_find_sl_bear using the per-bar level
    snapshot on the BarView (v.ssl_levels / v.bsl_levels = [(price, swept)])."""
    if direction == BULL:
        if np.isfinite(fvg_bound):
            c1 = fvg_bound - buf
            if c1 < entry:
                return c1
        best = np.nan
        for price, swept in v.ssl_levels:            # swept SSL below entry
            if swept:
                p = price - buf
                if p < entry and (not np.isfinite(best) or p > best):
                    best = p
        if not np.isfinite(best):
            for price, swept in v.ssl_levels:
                if not swept:
                    p = price - buf
                    if p < entry and (not np.isfinite(best) or p > best):
                        best = p
        if not np.isfinite(best):
            best = entry - atrv * 1.5
        return best
    else:
        if np.isfinite(fvg_bound):
            c1 = fvg_bound + buf
            if c1 > entry:
                return c1
        best = np.nan
        for price, swept in v.bsl_levels:
            if swept:
                p = price + buf
                if p > entry and (not np.isfinite(best) or p < best):
                    best = p
        if not np.isfinite(best):
            for price, swept in v.bsl_levels:
                if not swept:
                    p = price + buf
                    if p > entry and (not np.isfinite(best) or p < best):
                        best = p
        if not np.isfinite(best):
            best = entry + atrv * 1.5
        return best


def _passes_filters(cfg, v, eng, i, direction, f, entry, atrv) -> bool:
    """Phase 5 signal-quality gates. Each is opt-in via Config."""
    # #1 — premium/discount equilibrium: longs only in discount (below the
    # 50% of the recent swing), shorts only in premium.
    if cfg.pd_filter and np.isfinite(v.equilibrium):
        if direction == BULL and entry > v.equilibrium:
            return False
        if direction == BEAR and entry < v.equilibrium:
            return False

    # #3 — sweep→FVG distance: the entry FVG must be a post-sweep gap whose
    # CE sits within dist_filter_atr ATR of the swept level that spawned it.
    if cfg.dist_filter_atr > 0:
        if not f.post_sweep:
            return False
        swept_px = v.last_ssl_sweep_px if direction == BULL else v.last_bsl_sweep_px
        if not np.isfinite(swept_px) or not np.isfinite(atrv) or atrv <= 0:
            return False
        if abs(entry - swept_px) / atrv > cfg.dist_filter_atr:
            return False

    # #2 — regime: skip chop (ATR pctile < 20) and chaos (> 95)
    if cfg.regime_filter:
        p = eng.atr_pctile[i]
        if not np.isfinite(p) or p < 20.0 or p > 95.0:
            return False

    # #4 — entry-candle quality: signal candle bar[1] must be a decisive,
    # correctly-directed body.
    if cfg.candle_filter > 0:
        o1, h1, l1, c1 = (eng._off(a, i, 1) for a in (eng.o, eng.h, eng.l, eng.c))
        rng = h1 - l1
        if not (np.isfinite(c1) and rng > 0):
            return False
        body_pct = abs(c1 - o1) / rng
        if body_pct < cfg.candle_filter:
            return False
        if direction == BULL and c1 <= o1:
            return False
        if direction == BEAR and c1 >= o1:
            return False
    return True


TERMINAL = {"tp2", "sl", "be", "expired", "invalid", "timeout", ""}


def _make_trade(cfg, v, eng, i, direction, f, sc, source, l1, h1, atrv, buf,
                min_risk, max_risk):
    """Build a Trade for the configured entry model, or return None."""
    sign = 1 if direction == BULL else -1
    bound = f.bot if direction == BULL else f.top

    if cfg.entry_model == "market":
        entry = eng.o[i]                       # next-bar open after the signal
    elif cfg.entry_model == "edge_limit":
        entry = f.top if direction == BULL else f.bot
    else:                                      # ce_limit (Pine default)
        entry = f.ce

    sl = _find_sl(v, atrv, direction, entry, bound, buf)
    risk = abs(entry - sl)
    ok_side = (sl < entry) if direction == BULL else (sl > entry)
    if not (ok_side and min_risk <= risk <= max_risk):
        return None
    if not _passes_filters(cfg, v, eng, i, direction, f, entry, atrv):
        return None

    t = Trade(direction, entry, sl,
              entry + risk * cfg.tp1_rr * sign,
              entry + risk * cfg.tp2_rr * sign,
              risk, i, sc, f.bot, f.top, f, source, PENDING)

    if cfg.entry_model == "market":
        t.state = ACTIVE; t.activate_bar = i; t.entry_score = sc
    else:
        touched = (np.isfinite(l1) and l1 <= entry) if direction == BULL \
            else (np.isfinite(h1) and h1 >= entry)
        if touched:
            t.state = ACTIVE; t.activate_bar = i; t.entry_score = sc
    return t


def run_trades(eng: Engine, views, cfg=None):
    cfg = cfg or eng.cfg
    trades: list[Trade] = []
    cur: Trade | None = None
    last_bull_sig = last_bear_sig = -10**9
    last_setup_bar = -10**9
    scores = []

    for i, v in enumerate(views):
        if not np.isfinite(eng.atr[i]) or i < cfg.atr_len + cfg.swing_lb + 3:
            scores.append((0, 0))
            continue
        bull, bear = score_bar(v, eng, i)
        scores.append((bull, bear))
        atrv = eng.atr[i]
        buf = atrv * cfg.sl_buffer_atr
        min_risk = atrv * cfg.min_risk_atr
        max_risk = atrv * cfg.max_sl_atr

        h1 = eng._off(eng.h, i, 1)
        l1 = eng._off(eng.l, i, 1)
        c1 = eng._off(eng.c, i, 1)
        h2 = eng._off(eng.h, i, 2)
        l2 = eng._off(eng.l, i, 2)

        active_slot = cur is not None and cur.state in (PENDING, ACTIVE, TP1_HIT)
        setup_created_this_bar = False

        # ── 15.4/15.5 signal generation ──────────────────────
        sig_bull = (bull >= cfg.conf_threshold and bull > bear
                    and (i - last_bull_sig) >= cfg.signal_cooldown
                    and v.bias in (BULL, NONE))
        sig_bear = (bear >= cfg.conf_threshold and bear > bull
                    and (i - last_bear_sig) >= cfg.signal_cooldown
                    and v.bias in (BEAR, NONE))
        if sig_bull:
            last_bull_sig = i
        if sig_bear:
            last_bear_sig = i

        can_create = not active_slot

        # ── 16.5 setup creation from confluence signal ───────
        if can_create and (sig_bull or sig_bear):
            direction = BULL if sig_bull else BEAR
            fvgs = v.bull_fvgs if direction == BULL else v.bear_fvgs
            f = _best_fvg(fvgs, eng.c[i])
            if f:
                sc = bull if direction == BULL else bear
                t = _make_trade(cfg, v, eng, i, direction, f, sc, "signal",
                                l1, h1, atrv, buf, min_risk, max_risk)
                if t is not None:
                    cur = t
                    trades.append(t)
                    last_setup_bar = i
                    setup_created_this_bar = True

        # ── 16.6 pending setup monitoring ───────────────────
        if cur is not None and cur.state == PENDING and not setup_created_this_bar:
            fvg_invalid = cur.fvg_ref is not None and cur.fvg_ref.state == MITIGATED
            bias_invalid = ((cur.dir == BULL and v.bias == BEAR)
                            or (cur.dir == BEAR and v.bias == BULL))
            if cur.dir == BULL:
                ce_touched = np.isfinite(c1) and l1 <= cur.entry and c1 > cur.fvg_bot
            else:
                ce_touched = np.isfinite(c1) and h1 >= cur.entry and c1 < cur.fvg_top
            if fvg_invalid or bias_invalid:
                cur.outcome, cur.state, cur.exit_bar = "invalid", "invalid", i
                cur = None
            elif ce_touched:
                sc = bull if cur.dir == BULL else bear
                if sc >= cfg.entry_min_score:
                    cur.state = ACTIVE
                    cur.activate_bar = i
                    cur.entry_score = sc
                else:
                    cur.outcome, cur.state, cur.exit_bar = "invalid", "invalid", i
                    cur = None
            elif i - cur.created_bar > cfg.setup_max_age:
                cur.outcome, cur.state, cur.exit_bar = "expired", "expired", i
                cur = None

        # ── 16.7 FVG retest — same pipeline ─────────────────
        retest_slot_open = (not sig_bull and not sig_bear and not setup_created_this_bar
                            and (cur is None or cur.state in TERMINAL)
                            and v.active_session
                            and (i - last_setup_bar) > cfg.retest_cooldown)
        if retest_slot_open and v.bias in (BULL, BEAR):
            direction = v.bias
            fvgs = v.bull_fvgs if direction == BULL else v.bear_fvgs
            for f in fvgs:
                if f.state not in (FRESH, FIRST_TOUCH, CE_TOUCH):
                    continue
                if direction == BULL:
                    entered = (np.isfinite(l1) and np.isfinite(l2)
                               and l1 <= f.top and c1 >= f.bot and l2 > f.top)
                else:
                    entered = (np.isfinite(h1) and np.isfinite(h2)
                               and h1 >= f.bot and c1 <= f.top and h2 < f.bot)
                if not entered:
                    continue
                sc = bull if direction == BULL else bear
                if sc < cfg.entry_min_score:
                    break
                t = _make_trade(cfg, v, eng, i, direction, f, sc, "retest",
                                l1, h1, atrv, buf, min_risk, max_risk)
                if t is None:
                    break
                cur = t
                trades.append(t)
                last_setup_bar = i
                setup_created_this_bar = True
                break

        # ── 16.8 trade monitoring ──────────────────────────
        # fill_strict: skip the activation bar so the candle used to fill the
        # entry (bar[1] at activation) can't also register the exit.
        monitor_ok = not (cfg.fill_strict and cur is not None and i <= cur.activate_bar)
        if monitor_ok and cur is not None and cur.state in (ACTIVE, TP1_HIT):
            if cur.dir == BULL:
                hit_sl = (l1 <= cur.entry) if cur.state == TP1_HIT else (l1 <= cur.sl)
                hit_tp2 = h1 >= cur.tp2
                hit_tp1 = (not hit_tp2) and h1 >= cur.tp1
            else:
                hit_sl = (h1 >= cur.entry) if cur.state == TP1_HIT else (h1 >= cur.sl)
                hit_tp2 = l1 <= cur.tp2
                hit_tp1 = (not hit_tp2) and l1 <= cur.tp1

            if hit_sl:
                if cur.state == TP1_HIT:
                    cur.outcome, cur.r, cur.state = "be", cfg.tp1_rr * 0.5, "be"
                else:
                    cur.outcome, cur.r, cur.state = "sl", -1.0, "sl"
                cur.exit_bar = i
                cur = None
            elif hit_tp2:
                cur.outcome, cur.r, cur.state = "tp2", cfg.tp2_rr, "tp2"
                cur.exit_bar = i
                cur = None
            elif hit_tp1 and cur.state == ACTIVE:
                cur.state = TP1_HIT
            elif i - cur.activate_bar > cfg.trade_max_age:
                # mark-to-market at bar[1] close so a filled trade that goes
                # nowhere counts as its real (usually small) P/L, not a
                # silently-dropped setup. R relative to initial risk.
                mtm = (c1 - cur.entry) / cur.risk if cur.dir == BULL else (cur.entry - c1) / cur.risk
                if cur.state == TP1_HIT:                 # half already banked at +1R
                    mtm = cfg.tp1_rr * 0.5 + max(mtm, 0.0) * 0.5
                cur.outcome, cur.r, cur.state, cur.exit_bar = "timeout", float(mtm), "timeout", i
                cur = None

    eng.scores = scores
    return trades


# ── metrics (Pine Section 17) ────────────────────────────────
def metrics(trades: list[Trade]) -> dict:
    # a "trade" for P/L = anything that actually filled (tp2/be/sl/timeout)
    closed = [t for t in trades if t.outcome in ("tp2", "be", "sl", "timeout")]
    tp2 = sum(t.outcome == "tp2" for t in closed)
    be = sum(t.outcome == "be" for t in closed)
    sl = sum(t.outcome == "sl" for t in closed)
    timeout = sum(t.outcome == "timeout" for t in closed)
    total = len(closed)
    wins = sum(t.r > 0 for t in closed)          # positive-R trades (incl. timeouts)
    r_total = sum(t.r for t in closed)
    r_wins = sum(t.r for t in closed if t.r > 0)

    eq = np.cumsum([t.r for t in closed]) if closed else np.array([0.0])
    peak = np.maximum.accumulate(eq)
    max_dd = float((peak - eq).max()) if closed else 0.0

    return {
        "trades": total,
        "tp2_full": tp2,
        "tp1_be": be,
        "sl": sl,
        "timeout": timeout,
        "win_pct": round(100 * wins / total, 1) if total else 0.0,
        "total_r": round(r_total, 2),
        "expectancy_r": round(r_total / total, 3) if total else 0.0,
        "avg_win_r": round(r_wins / wins, 2) if wins else 0.0,
        "max_dd_r": round(max_dd, 2),
        "avg_entry_score": round(np.mean([t.entry_score for t in closed]), 1) if total else 0.0,
        "setups_created": len(trades),
        "from_signal": sum(t.source == "signal" for t in trades),
        "from_retest": sum(t.source == "retest" for t in trades),
        "expired_or_invalid": len(trades) - total,
    }
