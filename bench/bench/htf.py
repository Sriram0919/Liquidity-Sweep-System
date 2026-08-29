"""Section 6 + 6B — HTF Structure & HTF FVG / Order Block engine.

Port of LSS-Pro.pine Sections 6 and 6B. For a 5m chart `fn_resolve_htf`
maps to 1H, so the LTF candles are resampled to `cfg.htf_period` and the
HTF engine is stepped as each HTF bar closes.

Pine fidelity:
  * request.security(..., lookahead_off) → the HTF value seen on an LTF bar
    is the LAST CLOSED HTF bar. We advance HTF state only when an HTF bar
    has fully closed relative to the current LTF timestamp.
  * HTF pivots: ta.pivothigh(high, 3, 3) on the HTF series — confirmed 3 HTF
    bars later (ind.pivot_high already places the value on the confirm bar).
  * 6B.4 HTF-FVG state (CE touch / mitigation) is evaluated on every LTF bar
    using LTF low/high/close — exactly as the Pine (`low <= HTF_FVG_BULL_CE`).

Outputs per LTF bar (HTFView): the booleans Section 15 scoring consumes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import indicators as ind

_MITIGATED = "Mitigated"
_CE_TOUCH = "CE Touch"
_FRESH = "Fresh"
_NONE = "None"


@dataclass
class HTFView:
    bias: str = "—"                       # "Bullish" / "Bearish" / "—"
    fvg_bull_active: bool = False
    fvg_bull_ce_near: bool = False
    fvg_bear_active: bool = False
    fvg_bear_ce_near: bool = False
    ob_bull_near: bool = False
    ob_bear_near: bool = False


BIAS_BULL, BIAS_BEAR, BIAS_NONE = "Bullish", "Bearish", "—"


class HTFEngine:
    def __init__(self, df: pd.DataFrame, cfg):
        self.cfg = cfg
        d = df[["date", "open", "high", "low", "close", "volume"]].copy()
        d["date"] = pd.to_datetime(d["date"], utc=True)
        g = (d.resample(cfg.htf_period, on="date", label="left", closed="left")
               .agg({"open": "first", "high": "max", "low": "min",
                     "close": "last", "volume": "sum"})
               .dropna(subset=["open"]))
        self.htf = g.reset_index()
        self.h_open = self.htf["open"].to_numpy(float)
        self.h_high = self.htf["high"].to_numpy(float)
        self.h_low = self.htf["low"].to_numpy(float)
        self.h_close = self.htf["close"].to_numpy(float)
        self.h_start = self.htf["date"].to_numpy("datetime64[ns]")
        period = pd.Timedelta(cfg.htf_period).to_timedelta64()
        self.h_end = self.h_start + period
        lb = cfg.htf_pivot_lb
        self.h_piv_h = ind.pivot_high(self.htf["high"], lb, lb).to_numpy(float)
        self.h_piv_l = ind.pivot_low(self.htf["low"], lb, lb).to_numpy(float)

        # ── Section 6 state ────────────────────────────────────
        self.last_sh = np.nan
        self.last_sl = np.nan
        self._k = -1                       # last-closed HTF bar index seen

        # ── Section 6B state (1 active FVG per side) ───────────
        self.fb_top = self.fb_bot = self.fb_ce = np.nan
        self.fb_state = _NONE
        self.fb_ob_top = self.fb_ob_bot = np.nan
        self.se_top = self.se_bot = self.se_ce = np.nan
        self.se_state = _NONE
        self.se_ob_top = self.se_ob_bot = np.nan

    def _advance_htf(self, k: int):
        """Run Section 6.2/6.3 + 6B.3 for every HTF bar newly closed up to k."""
        for kk in range(self._k + 1, k + 1):
            # 6.2 track last confirmed HTF swing
            if np.isfinite(self.h_piv_h[kk]):
                self.last_sh = self.h_piv_h[kk]
            if np.isfinite(self.h_piv_l[kk]):
                self.last_sl = self.h_piv_l[kk]
            # 6B.3 register a fresh HTF FVG when this HTF bar completes
            if kk >= 2:
                o1, c1 = self.h_open[kk - 1], self.h_close[kk - 1]
                h0, l0 = self.h_high[kk], self.h_low[kk]
                h2, l2 = self.h_high[kk - 2], self.h_low[kk - 2]
                o2, c2 = self.h_open[kk - 2], self.h_close[kk - 2]
                if h2 < l0 and c1 > o1:                       # bull HTF FVG
                    self.fb_top, self.fb_bot = l0, h2
                    self.fb_ce = (l0 + h2) / 2.0
                    self.fb_state = _FRESH
                    if c2 < o2:
                        self.fb_ob_top, self.fb_ob_bot = o2, c2
                    else:
                        self.fb_ob_top = self.fb_ob_bot = np.nan
                if l2 > h0 and c1 < o1:                       # bear HTF FVG
                    self.se_top, self.se_bot = l2, h0
                    self.se_ce = (l2 + h0) / 2.0
                    self.se_state = _FRESH
                    if c2 > o2:
                        self.se_ob_top, self.se_ob_bot = c2, o2
                    else:
                        self.se_ob_top = self.se_ob_bot = np.nan
        self._k = k

    def step(self, ts, low, high, close, atr) -> HTFView:
        # how many HTF bars have fully closed as of this LTF timestamp
        t = np.datetime64(ts.tz_convert("UTC").tz_localize(None))
        k = int(np.searchsorted(self.h_end, t, side="right")) - 1
        if k < 0:
            return HTFView()
        if k > self._k:
            self._advance_htf(k)

        htf_close = self.h_close[k]

        # ── 6.3 HTF bias from structure breaks ─────────────────
        if np.isfinite(self.last_sh) and htf_close > self.last_sh:
            bias = BIAS_BULL
        elif np.isfinite(self.last_sl) and htf_close < self.last_sl:
            bias = BIAS_BEAR
        else:
            bias = BIAS_NONE

        # ── 6B.4 HTF FVG state updates (LTF resolution) ────────
        if self.fb_state not in (_NONE, _MITIGATED):
            if np.isfinite(self.fb_ce) and low <= self.fb_ce:
                self.fb_state = _CE_TOUCH
            if np.isfinite(self.fb_bot) and low <= self.fb_bot:
                self.fb_state = _MITIGATED
        if self.se_state not in (_NONE, _MITIGATED):
            if np.isfinite(self.se_ce) and high >= self.se_ce:
                self.se_state = _CE_TOUCH
            if np.isfinite(self.se_top) and high >= self.se_top:
                self.se_state = _MITIGATED
        # HTF OB mitigation — close through the body
        if np.isfinite(self.fb_ob_bot) and close < self.fb_ob_bot:
            self.fb_ob_top = self.fb_ob_bot = np.nan
        if np.isfinite(self.se_ob_top) and close > self.se_ob_top:
            self.se_ob_top = self.se_ob_bot = np.nan

        v = HTFView(bias=bias)
        a = atr if (atr is not None and np.isfinite(atr)) else 0.0
        v.fvg_bull_active = self.fb_state not in (_NONE, _MITIGATED)
        v.fvg_bear_active = self.se_state not in (_NONE, _MITIGATED)
        v.fvg_bull_ce_near = v.fvg_bull_active and np.isfinite(self.fb_ce) and abs(close - self.fb_ce) <= a * 0.5
        v.fvg_bear_ce_near = v.fvg_bear_active and np.isfinite(self.se_ce) and abs(close - self.se_ce) <= a * 0.5
        v.ob_bull_near = (np.isfinite(self.fb_ob_top) and np.isfinite(self.fb_ob_bot)
                          and low <= self.fb_ob_top and high >= self.fb_ob_bot)
        v.ob_bear_near = (np.isfinite(self.se_ob_top) and np.isfinite(self.se_ob_bot)
                          and low <= self.se_ob_top and high >= self.se_ob_bot)
        return v
