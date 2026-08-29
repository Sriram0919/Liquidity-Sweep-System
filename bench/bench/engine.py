"""Bar-by-bar port of the LSS Pro signal core.

Pine semantics preserved:
  * Detection runs on the CURRENT bar using CONFIRMED bars [1],[2],[3]
    (offsets into the past). Nothing here reads bar i's own close to make a
    decision at bar i except VWAP/RSI-style running indicators (as in Pine).
  * `bar[1]` == row i-1, `bar[2]` == i-2, `bar[3]` == i-3.

Ported: Section 12 (liquidity + sweep grading + PDH/PDL + inducement),
Section 12.5 (displacement), Section 13 (FVG 5-state), Section 15 (scoring,
reduced-component — see scoring.py).

Not ported for the PoC: Section 6/6B HTF, Section 14 BOS/CHoCH, Section 14.9
OTE, Section 11.5 news, Section 13B order blocks. StructureBias is a swing
proxy (structure.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from . import indicators as ind
from .structure import StructureBias, BULL, BEAR, NONE

SWEEP_A, SWEEP_B, SWEEP_C = 3, 2, 1
FRESH, FIRST_TOUCH, CE_TOUCH, DEEP_RETEST, MITIGATED = (
    "Fresh", "First Touch", "CE Touch", "Deep Retest", "Mitigated",
)


@dataclass
class Level:
    price: float
    bar: int
    volume: float
    swept: bool = False
    swept_bar: int = 0
    grade: int = SWEEP_C


@dataclass
class FVG:
    top: float
    bot: float
    ce: float
    bar: int
    state: str = FRESH
    grade: str = "S"
    mit_bar: int = 0
    post_sweep: bool = False


@dataclass
class BarView:
    """Signal state published on a given bar (consumed by scoring / trade)."""
    i: int
    date: pd.Timestamp
    close: float
    atr: float
    bias: str
    evt_bsl_swept: bool = False
    evt_ssl_swept: bool = False
    last_bsl_grade: int = SWEEP_C
    last_ssl_grade: int = SWEEP_C
    pdh_swept: bool = False
    pdl_swept: bool = False
    indu_bsl: bool = False
    indu_ssl: bool = False
    bull_fvgs: list = field(default_factory=list)
    bear_fvgs: list = field(default_factory=list)


class Engine:
    def __init__(self, df: pd.DataFrame, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.df = df.reset_index(drop=True)
        n = len(self.df)
        self.o = self.df["open"].to_numpy(float)
        self.h = self.df["high"].to_numpy(float)
        self.l = self.df["low"].to_numpy(float)
        self.c = self.df["close"].to_numpy(float)
        self.v = self.df["volume"].to_numpy(float)
        self.dt = pd.to_datetime(self.df["date"], utc=True)

        self.atr = ind.atr(self.df, self.cfg.atr_len).to_numpy(float)
        self.vol_sma = ind.sma(self.df["volume"], self.cfg.vol_len).to_numpy(float)
        self.rsi = ind.rsi(self.df["close"], self.cfg.rsi_len).to_numpy(float)
        self.vwap = ind.session_vwap(self.df).to_numpy(float)
        self.piv_h = ind.pivot_high(self.df["high"], self.cfg.swing_lb, self.cfg.swing_lb).to_numpy(float)
        self.piv_l = ind.pivot_low(self.df["low"], self.cfg.swing_lb, self.cfg.swing_lb).to_numpy(float)

        self.day = self.dt.dt.tz_convert("Asia/Kolkata").dt.normalize().to_numpy()

        self.bsl: list[Level] = []
        self.ssl: list[Level] = []
        self.bull_fvg: list[FVG] = []
        self.bear_fvg: list[FVG] = []
        self.bias_engine = StructureBias()

        self.last_ssl_sweep_bar = -10**9
        self.last_bsl_sweep_bar = -10**9
        self.last_ssl_grade = SWEEP_C
        self.last_bsl_grade = SWEEP_C

        # PDH/PDL
        self._prev_day_high: float | None = None
        self._prev_day_low: float | None = None
        self._cur_day = None
        self._cur_day_high = -np.inf
        self._cur_day_low = np.inf
        self.pdh_swept_bar = -10**9
        self.pdl_swept_bar = -10**9

        # inducement
        self.indu_bsl_last = 0
        self.indu_ssl_last = 0
        self.indu_bsl_count = 0
        self.indu_ssl_count = 0

        self._sweep_hist: list[tuple[int, str]] = []  # (bar, 'BSL'|'SSL')

    # ── helpers ────────────────────────────────────────────────
    def _off(self, arr, i, k):
        j = i - k
        return arr[j] if j >= 0 else np.nan

    # ── per-bar processing ────────────────────────────────────
    def _roll_day(self, i):
        d = self.day[i]
        if self._cur_day is None:
            self._cur_day = d
        elif d != self._cur_day:
            self._prev_day_high = self._cur_day_high if np.isfinite(self._cur_day_high) else None
            self._prev_day_low = self._cur_day_low if np.isfinite(self._cur_day_low) else None
            self._cur_day = d
            self._cur_day_high = -np.inf
            self._cur_day_low = np.inf
        self._cur_day_high = max(self._cur_day_high, self.h[i])
        self._cur_day_low = min(self._cur_day_low, self.l[i])

    def _displacement(self, i):
        """Pine 12: metrics on bar[1]."""
        cfg = self.cfg
        o1, h1, l1, c1, v1 = (self._off(a, i, 1) for a in (self.o, self.h, self.l, self.c, self.v))
        atrv = self.atr[i]
        vsma = self.vol_sma[i]
        if not np.isfinite(o1) or not np.isfinite(atrv) or not np.isfinite(vsma):
            return False, False
        body = abs(c1 - o1)
        rng = h1 - l1
        body_pct = body / rng if rng > 0 else 0.0
        range_atr = rng / atrv if atrv > 0 else 0.0
        vol_ratio = v1 / vsma if vsma > 0 else 0.0
        ok = (body_pct >= cfg.disp_body_min and range_atr >= cfg.disp_range_min
              and vol_ratio >= cfg.disp_vol_min)
        return (ok and c1 >= o1), (ok and c1 < o1)

    def _manage_levels(self, i):
        cfg = self.cfg
        lb = cfg.swing_lb
        eq_tol = cfg.eq_tol_ticks * cfg.mintick
        sh = self.piv_h[i]
        sl = self.piv_l[i]
        pivot_bar = i - lb
        if np.isfinite(sh):
            unswept = [x for x in self.bsl if not x.swept]
            if not any(abs(x.price - sh) <= eq_tol for x in unswept):
                if len(self.bsl) >= cfg.max_levels:
                    self.bsl.pop(0)
                self.bsl.append(Level(price=sh, bar=pivot_bar, volume=self._off(self.v, i, lb)))
        if np.isfinite(sl):
            unswept = [x for x in self.ssl if not x.swept]
            if not any(abs(x.price - sl) <= eq_tol for x in unswept):
                if len(self.ssl) >= cfg.max_levels:
                    self.ssl.pop(0)
                self.ssl.append(Level(price=sl, bar=pivot_bar, volume=self._off(self.v, i, lb)))

    def _detect_sweeps(self, i, disp_bull, disp_bear):
        cfg = self.cfg
        h1, l1, c1 = self._off(self.h, i, 1), self._off(self.l, i, 1), self._off(self.c, i, 1)
        evt_bsl = evt_ssl = False
        if not np.isfinite(c1):
            return evt_bsl, evt_ssl

        def grade(levels, idx, wick_ok, disp_ok):
            vols = [x.volume for x in levels if np.isfinite(x.volume)]
            avg = sum(vols) / len(vols) if vols else 0.0
            vol_ok = avg > 0 and np.isfinite(levels[idx].volume) and levels[idx].volume >= avg
            f = int(wick_ok) + int(vol_ok) + int(disp_ok)
            return SWEEP_A if f == 3 else SWEEP_B if f >= 2 else SWEEP_C

        for idx, lv in enumerate(self.bsl):
            if lv.swept:
                continue
            if h1 > lv.price and c1 < lv.price:
                lv.swept = True
                lv.swept_bar = i - 1
                lv.grade = grade(self.bsl, idx, c1 < lv.price, disp_bear)
                self.last_bsl_grade = lv.grade
                self.last_bsl_sweep_bar = i
                evt_bsl = True
        for idx, lv in enumerate(self.ssl):
            if lv.swept:
                continue
            if l1 < lv.price and c1 > lv.price:
                lv.swept = True
                lv.swept_bar = i - 1
                lv.grade = grade(self.ssl, idx, c1 > lv.price, disp_bull)
                self.last_ssl_grade = lv.grade
                self.last_ssl_sweep_bar = i
                evt_ssl = True

        # expire swept levels
        self.bsl = [x for x in self.bsl if not (x.swept and i - x.swept_bar > cfg.swept_expiry)]
        self.ssl = [x for x in self.ssl if not (x.swept and i - x.swept_bar > cfg.swept_expiry)]

        # PDH/PDL (Pine 12: swept level within 2*ATR of prev-day extreme)
        tol = self.atr[i] * 2.0 if np.isfinite(self.atr[i]) else 0.0
        if evt_bsl and self._prev_day_high is not None:
            if abs(lv_price_of_last(self.bsl) - self._prev_day_high) <= tol:
                self.pdh_swept_bar = i
        if evt_ssl and self._prev_day_low is not None:
            if abs(lv_price_of_last(self.ssl) - self._prev_day_low) <= tol:
                self.pdl_swept_bar = i

        # inducement (Pine 12): 2 sweeps same side within conf_lookback*2 bars
        win = cfg.conf_lookback * 2
        if evt_bsl:
            self.indu_bsl_count = self.indu_bsl_count + 1 if i - self.indu_bsl_last <= win else 1
            self.indu_bsl_last = i
        if evt_ssl:
            self.indu_ssl_count = self.indu_ssl_count + 1 if i - self.indu_ssl_last <= win else 1
            self.indu_ssl_last = i
        if i - self.indu_bsl_last > 30:
            self.indu_bsl_count = 0
        if i - self.indu_ssl_last > 30:
            self.indu_ssl_count = 0
        return evt_bsl, evt_ssl

    def _fvg_grade(self, width):
        a = self.atr_cur
        if not np.isfinite(a) or a <= 0:
            return "S"
        return "L" if width >= a else "M" if width >= a * 0.5 else "S"

    def _detect_fvg(self, i, bias):
        cfg = self.cfg
        o = self.o; h = self.h; l = self.l; c = self.c
        a = self.atr_cur
        if i < 4 or not np.isfinite(a):
            return
        h3, l3 = self._off(h, i, 3), self._off(l, i, 3)
        h1, l1 = self._off(h, i, 1), self._off(l, i, 1)
        o1, c1 = self._off(o, i, 1), self._off(c, i, 1)
        o2, h2, l2, c2 = (self._off(x, i, 2) for x in (o, h, l, c))
        o3, c3 = self._off(o, i, 3), self._off(c, i, 3)

        # session gap filter (Pine 1465)
        tf_ms = int((self.dt.iloc[i] - self.dt.iloc[i - 1]).total_seconds() * 1000) if i >= 1 else 0
        gap_ok = (self.dt.iloc[i - 1] - self.dt.iloc[i - 3]).total_seconds() * 1000 <= tf_ms * cfg.fvg_session_gap_mult if i >= 3 and tf_ms else True

        # bullish
        c2b_body = abs(c2 - o2); c2b_range = h2 - l2
        c2_bull_ok = c2 > o2 and c2b_range > 0 and c2b_body / c2b_range >= cfg.fvg_body_pct
        bull_cnt = int(c1 > o1) + int(c2 > o2) + int(c3 > o3)
        bull_det = h3 < l1 and c2_bull_ok and gap_ok and bull_cnt >= 2
        if bull_det:
            top, bot = l1, h3
            width = top - bot
            if width >= a * cfg.fvg_min_atr and bias in (BULL, NONE):
                if len(self.bull_fvg) >= 5:
                    self.bull_fvg.pop(0)
                ps = (i - self.last_ssl_sweep_bar) <= cfg.fvg_sweep_win
                self.bull_fvg.append(FVG(top, bot, (top + bot) / 2, i, FRESH,
                                         self._fvg_grade(width), 0, ps))

        # bearish
        c2s_body = abs(c2 - o2); c2s_range = h2 - l2
        c2_bear_ok = c2 < o2 and c2s_range > 0 and c2s_body / c2s_range >= cfg.fvg_body_pct
        bear_cnt = int(c1 < o1) + int(c2 < o2) + int(c3 < o3)
        bear_det = l3 > h1 and c2_bear_ok and gap_ok and bear_cnt >= 2
        if bear_det:
            top, bot = l3, h1
            width = top - bot
            if width >= a * cfg.fvg_min_atr and bias in (BEAR, NONE):
                if len(self.bear_fvg) >= 5:
                    self.bear_fvg.pop(0)
                ps = (i - self.last_bsl_sweep_bar) <= cfg.fvg_sweep_win
                self.bear_fvg.append(FVG(top, bot, (top + bot) / 2, i, FRESH,
                                         self._fvg_grade(width), 0, ps))

    def _fvg_transitions(self, i):
        """Pine 13.7 — advance states on bar[1]. Forward-only."""
        l1, h1, c1 = self._off(self.l, i, 1), self._off(self.h, i, 1), self._off(self.c, i, 1)
        if not np.isfinite(c1):
            return
        for f in self.bull_fvg:
            if f.state == MITIGATED:
                continue
            if c1 <= f.bot:
                f.state = MITIGATED; f.mit_bar = i
            elif f.state == CE_TOUCH and c1 <= f.ce:
                f.state = DEEP_RETEST
            elif f.state in (FRESH, FIRST_TOUCH) and l1 <= f.ce:
                f.state = CE_TOUCH
            elif f.state == FRESH and l1 <= f.top and l1 > f.ce:
                f.state = FIRST_TOUCH
        for f in self.bear_fvg:
            if f.state == MITIGATED:
                continue
            if c1 >= f.top:
                f.state = MITIGATED; f.mit_bar = i
            elif f.state == CE_TOUCH and c1 >= f.ce:
                f.state = DEEP_RETEST
            elif f.state in (FRESH, FIRST_TOUCH) and h1 >= f.ce:
                f.state = CE_TOUCH
            elif f.state == FRESH and h1 >= f.bot and h1 < f.ce:
                f.state = FIRST_TOUCH

    def _fvg_expire(self, i):
        cfg = self.cfg
        def keep(f):
            if f.state == MITIGATED:
                return i - f.mit_bar <= cfg.fvg_mit_expiry
            return i - f.bar <= cfg.fvg_max_age
        self.bull_fvg = [f for f in self.bull_fvg if keep(f)]
        self.bear_fvg = [f for f in self.bear_fvg if keep(f)]

    # ── main ──────────────────────────────────────────────────
    def run(self):
        views: list[BarView] = []
        for i in range(len(self.df)):
            self.atr_cur = self.atr[i]
            self._roll_day(i)

            # confirmed pivots feed the structure proxy
            ph = self.piv_h[i]
            pl = self.piv_l[i]
            bias = self.bias_engine.update(ph if np.isfinite(ph) else None,
                                           pl if np.isfinite(pl) else None)

            disp_bull, disp_bear = self._displacement(i)
            self._manage_levels(i)
            evt_bsl, evt_ssl = self._detect_sweeps(i, disp_bull, disp_bear)
            self._detect_fvg(i, bias)
            self._fvg_transitions(i)
            self._fvg_expire(i)

            win = self.cfg.conf_lookback
            v = BarView(
                i=i, date=self.dt.iloc[i], close=self.c[i], atr=self.atr[i], bias=bias,
                evt_bsl_swept=evt_bsl, evt_ssl_swept=evt_ssl,
                last_bsl_grade=self.last_bsl_grade, last_ssl_grade=self.last_ssl_grade,
                pdh_swept=(i - self.pdh_swept_bar) <= 20,
                pdl_swept=(i - self.pdl_swept_bar) <= 20,
                indu_bsl=self.indu_bsl_count >= 2,
                indu_ssl=self.indu_ssl_count >= 2,
                bull_fvgs=[f for f in self.bull_fvg],
                bear_fvgs=[f for f in self.bear_fvg],
            )
            # recent-sweep recency (Pine 15.2 loops over lookback bars)
            v.recent_ssl_sweep = (i - self.last_ssl_sweep_bar) <= win
            v.recent_bsl_sweep = (i - self.last_bsl_sweep_bar) <= win
            views.append(v)
        return views


def lv_price_of_last(levels):
    for lv in reversed(levels):
        if lv.swept:
            return lv.price
    return float("nan")
