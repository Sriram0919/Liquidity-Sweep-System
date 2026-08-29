"""Setup lifecycle + TP1/TP2/BE/SL exit model — port of Pine Section 16 + 17.

Exit model (Pine 16.8) preserved exactly so R numbers are comparable to the
live Win-Rate Tracker:
  * monitoring evaluated on confirmed bar[1]
  * same-bar SL/TP  -> SL priority (conservative)
  * TP1 hit from ACTIVE -> move SL to breakeven (state TP1_HIT)
  * BE hit after TP1   -> partial win, R = tp1_rr * 0.5   (Pine 17.2 Bug D fix)
  * TP2 hit            -> full win,   R = tp2_rr
  * SL hit             -> loss,       R = -1.0

Divergences from live (PoC scope):
  * only confluence-signal setups; the FVG-retest pipeline (Pine 16.7) is
    not ported -> fewer trades than live.
  * best-FVG pick = active FVG (Fresh/First/CE) with CE nearest close;
    Pine's fn_best_*_fvg heuristic not yet read/ported.
  * SL finder mirrors fn_find_sl_bear (Pine 16): FVG boundary -> swept
    opposing level -> nearest unswept opposing level -> ATR*1.5 fallback.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .engine import Engine, BULL, BEAR, NONE, FRESH, FIRST_TOUCH, CE_TOUCH, MITIGATED
from .scoring import score_bar

NONE_ST, PENDING, ACTIVE, TP1_HIT = "none", "pending", "active", "tp1_hit"
CLOSED = {"tp2", "sl", "be", "expired", "invalid"}


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
    state: str = PENDING
    activate_bar: int = -1
    entry_score: int = 0
    exit_bar: int = -1
    outcome: str = ""
    r: float = 0.0


def _best_fvg(fvgs, close, want):
    """Prefer an FVG currently being tested (CE_TOUCH), then FIRST_TOUCH, then
    FRESH; within a state, the one whose CE is nearest price. Mirrors the
    live intent of entering the zone under test rather than a stale gap."""
    order = {CE_TOUCH: 0, FIRST_TOUCH: 1, FRESH: 2}
    cands = [f for f in fvgs if f.state in order]
    if not cands:
        return None
    return min(cands, key=lambda f: (order[f.state], abs(f.ce - close)))


def _find_sl(eng: Engine, i, direction, entry, fvg_bound, buf):
    """fvg_bound = fvg_bot (bull) or fvg_top (bear)."""
    if direction == BULL:
        c1 = fvg_bound - buf if np.isfinite(fvg_bound) else np.nan
        if np.isfinite(c1) and c1 < entry:
            return c1
        best = np.nan
        for lv in eng.ssl:                       # swept SSL below entry, closest
            if lv.swept:
                p = lv.price - buf
                if p < entry and (not np.isfinite(best) or p > best):
                    best = p
        if not np.isfinite(best):
            for lv in eng.ssl:
                if not lv.swept:
                    p = lv.price - buf
                    if p < entry and (not np.isfinite(best) or p > best):
                        best = p
        if not np.isfinite(best):
            best = entry - eng.atr[i] * 1.5
        return best
    else:
        c1 = fvg_bound + buf if np.isfinite(fvg_bound) else np.nan
        if np.isfinite(c1) and c1 > entry:
            return c1
        best = np.nan
        for lv in eng.bsl:
            if lv.swept:
                p = lv.price + buf
                if p > entry and (not np.isfinite(best) or p < best):
                    best = p
        if not np.isfinite(best):
            for lv in eng.bsl:
                if not lv.swept:
                    p = lv.price + buf
                    if p > entry and (not np.isfinite(best) or p < best):
                        best = p
        if not np.isfinite(best):
            best = entry + eng.atr[i] * 1.5
        return best


def run_trades(eng: Engine, views, cfg=None):
    cfg = cfg or eng.cfg
    trades: list[Trade] = []
    cur: Trade | None = None
    last_bull_sig = last_bear_sig = -10**9
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

        # ── monitor open trade (Pine 16.8) ───────────────────
        if cur and cur.state in (ACTIVE, TP1_HIT):
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
                cur.outcome, cur.state = "expired", "expired"
                cur.exit_bar = i
                cur = None

        # ── manage pending setup (Pine 16.6) ─────────────────
        if cur and cur.state == PENDING:
            mit = all(f.state == MITIGATED for f in (
                v.bull_fvgs if cur.dir == BULL else v.bear_fvgs)) if (
                v.bull_fvgs if cur.dir == BULL else v.bear_fvgs) else True
            bias_flip = (cur.dir == BULL and v.bias == BEAR) or (cur.dir == BEAR and v.bias == BULL)
            if cur.dir == BULL:
                ce_touched = np.isfinite(c1) and l1 <= cur.entry and c1 > cur.fvg_bot
            else:
                ce_touched = np.isfinite(c1) and h1 >= cur.entry and c1 < cur.fvg_top
            if mit or bias_flip:
                cur.outcome, cur.state = "invalid", "invalid"
                cur.exit_bar = i
                cur = None
            elif ce_touched:
                sc = bull if cur.dir == BULL else bear
                if sc >= cfg.entry_min_score:
                    cur.state = ACTIVE
                    cur.activate_bar = i
                    cur.entry_score = sc
                else:
                    cur.outcome, cur.state = "invalid", "invalid"
                    cur.exit_bar = i
                    cur = None
            elif i - cur.created_bar > cfg.setup_max_age:
                cur.outcome, cur.state = "expired", "expired"
                cur.exit_bar = i
                cur = None

        # ── new setup from confluence signal (Pine 16.5) ─────
        can_create = cur is None
        if can_create:
            sig_bull = bull >= cfg.conf_threshold and bull > bear and (i - last_bull_sig) >= cfg.signal_cooldown and v.bias in (BULL, NONE)
            sig_bear = bear >= cfg.conf_threshold and bear > bull and (i - last_bear_sig) >= cfg.signal_cooldown and v.bias in (BEAR, NONE)
            new = None
            if sig_bull:
                f = _best_fvg(v.bull_fvgs, eng.c[i], BULL)
                if f:
                    entry = f.ce
                    sl = _find_sl(eng, i, BULL, entry, f.bot, buf)
                    risk = abs(entry - sl)
                    if sl < entry and min_risk <= risk <= max_risk:
                        new = Trade(BULL, entry, sl, entry + risk * cfg.tp1_rr,
                                    entry + risk * cfg.tp2_rr, risk, i, bull, f.bot, f.top)
                        last_bull_sig = i
            elif sig_bear:
                f = _best_fvg(v.bear_fvgs, eng.c[i], BEAR)
                if f:
                    entry = f.ce
                    sl = _find_sl(eng, i, BEAR, entry, f.top, buf)
                    risk = abs(sl - entry)
                    if sl > entry and min_risk <= risk <= max_risk:
                        new = Trade(BEAR, entry, sl, entry - risk * cfg.tp1_rr,
                                    entry - risk * cfg.tp2_rr, risk, i, bear, f.bot, f.top)
                        last_bear_sig = i
            if new:
                # same-bar CE (Pine 3151 / 3242-style)
                if new.dir == BULL and np.isfinite(l1) and l1 <= new.entry:
                    new.state = ACTIVE
                    new.activate_bar = i
                    new.entry_score = bull
                elif new.dir == BEAR and np.isfinite(h1) and h1 >= new.entry:
                    new.state = ACTIVE
                    new.activate_bar = i
                    new.entry_score = bear
                cur = new
                trades.append(new)

    eng.scores = scores
    return trades


# ── metrics (Pine Section 17) ────────────────────────────────
def metrics(trades: list[Trade]) -> dict:
    closed = [t for t in trades if t.outcome in ("tp2", "be", "sl")]
    tp2 = sum(t.outcome == "tp2" for t in closed)
    be = sum(t.outcome == "be" for t in closed)
    sl = sum(t.outcome == "sl" for t in closed)
    total = len(closed)
    wins = tp2 + be
    r_total = sum(t.r for t in closed)
    r_wins = sum(t.r for t in closed if t.outcome in ("tp2", "be"))

    # equity curve / max drawdown in R
    eq = np.cumsum([t.r for t in closed]) if closed else np.array([0.0])
    peak = np.maximum.accumulate(eq)
    max_dd = float((peak - eq).max()) if closed else 0.0

    return {
        "trades": total,
        "tp2_full": tp2,
        "tp1_be": be,
        "sl": sl,
        "win_pct": round(100 * wins / total, 1) if total else 0.0,
        "total_r": round(r_total, 2),
        "expectancy_r": round(r_total / total, 3) if total else 0.0,
        "avg_win_r": round(r_wins / wins, 2) if wins else 0.0,
        "max_dd_r": round(max_dd, 2),
        "avg_entry_score": round(np.mean([t.entry_score for t in closed]), 1) if total else 0.0,
        "setups_created": len(trades),
        "expired_or_invalid": len(trades) - total,
    }
