"""All tunables, mirrored 1:1 from the `input.*` defaults in LSS-Pro.pine.

Line refs are to LSS-Pro.pine @ v3.2.0. Keep this in sync when the Pine
inputs change — the whole point of the bench is comparability.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # ── Liquidity / swings (Pine 264, 266) ──────────────────────
    swing_lb: int = 5              # IN_SWING_LB
    eq_tol_ticks: float = 3.0      # IN_EQ_TOL  (× mintick)
    swept_expiry: int = 30         # IN_SWEPT_EXPIRY
    max_levels: int = 5            # FIFO cap per side (Pine: array.size >= 5)

    # ── Market Structure — Section 14 (Pine 353, 355) ─────────
    ms_swing_lb: int = 5          # IN_MS_SWING_LB
    ms_max_lines: int = 3         # IN_MS_MAX_LINES (FIFO break history)
    choch_disp_pct: float = 0.75  # IN_CHOCH_DISP_PCT (CHoCH+ body % gate)

    # ── HTF engine — Section 6 / 6B (Pine 251, 458) ───────────
    htf_period: str = "60min"    # RESOLVED_HTF for a 5m chart (fn_resolve_htf)
    htf_pivot_lb: int = 3        # Pine 6.1: ta.pivothigh(high, 3, 3) on HTF

    # ── OTE lookback multiplier — Pine _ote_tf_mult (14.9) ────
    # 5m:16  15/30m:12  1H:8  — set with the chart TF of the CSV
    ote_tf_mult: int = 16

    # ── Order Blocks — Section 13B (Pine 315-324) ─────────────
    ob_lookback: int = 5         # IN_OB_LOOKBACK
    ob_body_only: bool = True    # IN_OB_BODY_ONLY
    ob_max_age: int = 50         # IN_OB_MAX_AGE
    ob_mit_expiry: int = 10      # IN_OB_MIT_EXPIRY

    # ── Retest pipeline — Section 16.7 ───────────────────────
    retest_cooldown: int = 3     # RETEST_COOLDOWN

    # ── Instrument mode ─────────────────────────────────────
    volume_blind: bool = False   # index spot: no real volume — degrade vol gates

    # ── Entry model (Wave 6 experiment) ─────────────────────
    #   "ce_limit"   — Pine default: limit at FVG midpoint, wait for retrace
    #   "edge_limit" — limit at the near FVG edge (shallower retrace fills)
    #   "market"     — enter at next-bar open on the signal, no wait
    entry_model: str = "ce_limit"

    # ── Phase 5 signal-quality filters (0 / False = off) ─────
    pd_filter: bool = False       # #1 premium/discount: longs in discount only
    dist_filter_atr: float = 0.0  # #3 sweep→FVG distance ceiling, in ATR (0 = off)
    regime_filter: bool = False   # #2 suppress when ATR pctile <20 (chop) / >95 (chaos)
    regime_lookback: int = 200    #    window for the ATR percentile
    candle_filter: float = 0.0    # #4 min body% of the signal candle bar[1] (0 = off)
    fill_strict: bool = True      # exit monitoring starts strictly AFTER the
                                  # activation bar (removes same-candle fill+exit)

    # ── Displacement (Pine 329, 332, 335, 405) ─────────────────
    disp_body_min: float = 0.7     # IN_DISP_BODY_MIN
    disp_range_min: float = 1.2    # IN_DISP_RANGE_MIN  (× ATR)
    disp_vol_min: float = 1.3      # IN_DISP_VOL_MIN    (× vol SMA)
    vol_len: int = 20              # IN_VOL_LEN

    # ── FVG (Pine 292, 295, 298, 302, 306) ────────────────────
    fvg_min_atr: float = 0.75      # IN_FVG_MIN_ATR
    fvg_body_pct: float = 0.75     # IN_FVG_BODY_PCT (impulse candle 2)
    fvg_max_age: int = 200         # IN_FVG_MAX_AGE
    fvg_sweep_win: int = 5         # IN_FVG_SWEEP_WIN (post-sweep tag window)
    fvg_mit_expiry: int = 20       # IN_FVG_MIT_EXPIRY
    fvg_session_gap_mult: int = 6  # Pine 1465: (time[1]-time[3]) <= tf*6

    # ── Confluence (Pine 361, 363, 423) ───────────────────────
    conf_threshold: int = 55      # IN_CONF_THRESHOLD (signal gate)
    conf_lookback: int = 5        # IN_CONF_LOOKBACK (event recency window)
    alert_min_score: int = 55     # IN_ALERT_MIN_SCORE

    # ── Indicators (Pine 402-406) ─────────────────────────────
    rsi_len: int = 14
    rsi_ob: int = 70
    rsi_os: int = 30
    vol_mult: float = 1.5         # IN_VOL_MULT (spike)

    # ── Trade model (Pine 375-392) ────────────────────────────
    tp1_rr: float = 1.0           # IN_TRADE_TP1_RR
    tp2_rr: float = 2.0           # IN_TRADE_TP2_RR
    sl_buffer_atr: float = 0.3    # IN_SL_BUFFER_ATR
    min_risk_atr: float = 0.5     # IN_MIN_RISK_ATR
    max_sl_atr: float = 2.5       # IN_MAX_SL_ATR
    setup_max_age: int = 20       # IN_SETUP_MAX_AGE
    trade_max_age: int = 50       # IN_TRADE_MAX_AGE
    entry_min_score: int = 40     # IN_ENTRY_MIN_SCORE

    # ── ATR ───────────────────────────────────────────────────
    atr_len: int = 14

    # ── Instrument ────────────────────────────────────────────
    mintick: float = 1.0          # MCX Crude Oil tick = ₹1

    # ── Signal cooldown (Pine 2849) ──────────────────────────
    signal_cooldown: int = 3

    # ── PoC divergences from Pine (documented, not yet ported) ─
    # Market structure (Section 14 BOS/CHoCH), HTF engine (6/6B),
    # OTE (14.9), news calendar (11.5), order blocks (13B).
    # scoring.py uses a reduced-component model; see its docstring.
