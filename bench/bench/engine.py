"""Bar-by-bar port of the LSS Pro signal core (full engine — Wave 5).

Pine semantics preserved:
  * Detection runs on the CURRENT bar using CONFIRMED bars [1],[2],[3].
  * `bar[1]` == row i-1, etc.
  * Per-bar section order matches the Pine file:
      13 (FVG detect + state)  →  14 (BOS/CHoCH, updates STRUCTURE_BIAS)
      →  14.8 counter-trend FVG purge  →  13B OB  →  6/6B HTF  →  14.9 OTE
    so the FVG structure-alignment filter (Section 13) sees STRUCTURE_BIAS
    as of the PREVIOUS bar — `ms.bias_before_update()`.

Ported: 12 (liquidity/sweep/PDH-PDL/inducement), 12.5 (displacement),
13 (FVG 5-state), 13B (order blocks), 14 (market structure — market_structure.py),
6/6B (HTF — htf.py), 14.9 (OTE — ote.py). Scoring: scoring.py (full 0-100).

Stubbed for the first baseline: 11.5 news + pre-positioning.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from . import indicators as ind
from . import ote as ote_mod
from .htf import HTFEngine, HTFView
from .market_structure import MarketStructure, BULL, BEAR, NONE

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
class OB:
    top: float
    bot: float
    bar: int
    state: str = FRESH      # FRESH -> "Tested" -> MITIGATED
    mit_bar: int = 0


@dataclass
class BarView:
    i: int
    date: pd.Timestamp
    close: float
    atr: float
    bias: str
    evt_bsl_swept: bool = False
    evt_ssl_swept: bool = False
    last_bsl_grade: int = SWEEP_C
    last_ssl_grade: int = SWEEP_C
    recent_bsl_sweep: bool = False
    recent_ssl_sweep: bool = False
    recent_bos_bull: bool = False
    recent_bos_bear: bool = False
    recent_choch_bull: bool = False
    recent_choch_bear: bool = False
    recent_choch_plus_bull: bool = False
    recent_choch_plus_bear: bool = False
    pdh_swept: bool = False
    pdl_swept: bool = False
    indu_bsl: bool = False
    indu_ssl: bool = False
    kill_zone: bool = False
    active_session: bool = False
    ctx_above: bool = False
    ctx_below: bool = False
    ote_price_in_zone: bool = False
    ote_fvg_ce_in: bool = False
    ob_bull_near: bool = False
    ob_bear_near: bool = False
    htf: HTFView = field(default_factory=HTFView)
    bull_fvgs: list = field(default_factory=list)
    bear_fvgs: list = field(default_factory=list)
    ssl_levels: list = field(default_factory=list)   # (price, swept)
    bsl_levels: list = field(default_factory=list)


class Engine:
    def __init__(self, df: pd.DataFrame, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.df = df.reset_index(drop=True)
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
        self.rsi_bull_div, self.rsi_bear_div = ind.rsi_divergence(self.df, self.rsi, 5)
        self.day = self.dt.dt.tz_convert("Asia/Kolkata").dt.normalize().to_numpy()

        # OTE rolling precompute (Section 14.9)
        self.ote_lb = self.cfg.ms_swing_lb * 16
        self._ote_rh, self._ote_rl, self._ote_ho, self._ote_lo = ote_mod.precompute(
            self.h, self.l, self.ote_lb)

        self.ms = MarketStructure(self.df, self.cfg)
        self.htf = HTFEngine(self.df, self.cfg)

        self.bsl: list[Level] = []
        self.ssl: list[Level] = []
        self.bull_fvg: list[FVG] = []
        self.bear_fvg: list[FVG] = []
        self.ob_bull: list[OB] = []
        self.ob_bear: list[OB] = []

        self.last_ssl_sweep_bar = -10**9
        self.last_bsl_sweep_bar = -10**9
        self.last_ssl_grade = SWEEP_C
        self.last_bsl_grade = SWEEP_C

        self._prev_day_high: float | None = None
        self._prev_day_low: float | None = None
        self._cur_day = None
        self._cur_day_high = -np.inf
        self._cur_day_low = np.inf
        self.pdh_swept_bar = -10**9
        self.pdl_swept_bar = -10**9

        self.indu_bsl_last = 0
        self.indu_ssl_last = 0
        self.indu_bsl_count = 0
        self.indu_ssl_count = 0

        # rolling structure-event history for the scoring lookback window
        self._ms_hist: list = []            # (bar, MSEvents)

    # ── helpers ────────────────────────────────────────────────
    def _off(self, arr, i, k):
        j = i - k
        return arr[j] if j >= 0 else np.nan

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
        cfg = self.cfg
        o1, h1, l1, c1, v1 = (self._off(a, i, 1) for a in (self.o, self.h, self.l, self.c, self.v))
        atrv = self.atr[i]
        vsma = self.vol_sma[i]
        if not np.isfinite(o1) or not np.isfinite(atrv):
            return False, False
        body = abs(c1 - o1)
        rng = h1 - l1
        body_pct = body / rng if rng > 0 else 0.0
        range_atr = rng / atrv if atrv > 0 else 0.0
        vol_ratio = v1 / vsma if (np.isfinite(vsma) and vsma > 0) else 0.0
        vol_ok = True if cfg.volume_blind else (vol_ratio >= cfg.disp_vol_min)
        ok = body_pct >= cfg.disp_body_min and range_atr >= cfg.disp_range_min and vol_ok
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
            if cfg.volume_blind:
                vol_ok = False
            else:
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

        self.bsl = [x for x in self.bsl if not (x.swept and i - x.swept_bar > cfg.swept_expiry)]
        self.ssl = [x for x in self.ssl if not (x.swept and i - x.swept_bar > cfg.swept_expiry)]

        tol = self.atr[i] * 2.0 if np.isfinite(self.atr[i]) else 0.0
        if evt_bsl and self._prev_day_high is not None:
            if abs(_lv_price_of_last(self.bsl) - self._prev_day_high) <= tol:
                self.pdh_swept_bar = i
        if evt_ssl and self._prev_day_low is not None:
            if abs(_lv_price_of_last(self.ssl) - self._prev_day_low) <= tol:
                self.pdl_swept_bar = i

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

        tf_ms = int((self.dt.iloc[i] - self.dt.iloc[i - 1]).total_seconds() * 1000) if i >= 1 else 0
        gap_ok = (self.dt.iloc[i - 1] - self.dt.iloc[i - 3]).total_seconds() * 1000 <= tf_ms * cfg.fvg_session_gap_mult if i >= 3 and tf_ms else True

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
                self._spawn_ob(i, BULL)

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
                self._spawn_ob(i, BEAR)

    def _spawn_ob(self, i, direction):
        """Section 13B — OB = last opposing candle before the displacement."""
        cfg = self.cfg
        found = -1
        for lb in range(3, 4 + cfg.ob_lookback):
            cl = self._off(self.c, i, lb)
            op = self._off(self.o, i, lb)
            if not np.isfinite(cl):
                break
            if direction == BULL and cl < op:
                found = lb; break
            if direction == BEAR and cl > op:
                found = lb; break
        if found < 0:
            return
        op = self._off(self.o, i, found)
        cl = self._off(self.c, i, found)
        hi = self._off(self.h, i, found)
        loo = self._off(self.l, i, found)
        if direction == BULL:
            top = op if cfg.ob_body_only else hi
            bot = cl if cfg.ob_body_only else loo
            lst = self.ob_bull
        else:
            top = cl if cfg.ob_body_only else hi
            bot = op if cfg.ob_body_only else loo
            lst = self.ob_bear
        if len(lst) >= 3:
            lst.pop(0)
        lst.append(OB(top, bot, i - found))

    def _ob_update(self, i):
        cfg = self.cfg
        l1, h1, c1 = self._off(self.l, i, 1), self._off(self.h, i, 1), self._off(self.c, i, 1)
        if np.isfinite(c1):
            for ob in self.ob_bull:
                if ob.state == MITIGATED:
                    continue
                ce = (ob.top + ob.bot) / 2.0
                if ob.state == FRESH and l1 <= ce and l1 >= ob.bot:
                    ob.state = "Tested"
                elif c1 < ob.bot:
                    ob.state = MITIGATED; ob.mit_bar = i
            for ob in self.ob_bear:
                if ob.state == MITIGATED:
                    continue
                ce = (ob.top + ob.bot) / 2.0
                if ob.state == FRESH and h1 >= ce and h1 <= ob.top:
                    ob.state = "Tested"
                elif c1 > ob.top:
                    ob.state = MITIGATED; ob.mit_bar = i

        def keep(ob):
            if ob.state == MITIGATED:
                return i - ob.mit_bar <= cfg.ob_mit_expiry
            return i - ob.bar <= cfg.ob_max_age
        self.ob_bull = [x for x in self.ob_bull if keep(x)]
        self.ob_bear = [x for x in self.ob_bear if keep(x)]

    def _fvg_transitions(self, i):
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

    def _session_flags(self, ts):
        """India cash session in UTC: 03:45-10:00 ; India KZ 03:45-04:30."""
        m = ts.hour * 60 + ts.minute
        active = 3 * 60 + 45 <= m < 10 * 60
        kz = 3 * 60 + 45 <= m < 4 * 60 + 30
        return active, kz

    # ── main ──────────────────────────────────────────────────
    def run(self):
        cfg = self.cfg
        views: list[BarView] = []
        for i in range(len(self.df)):
            self.atr_cur = self.atr[i]
            self._roll_day(i)

            bias_before = self.ms.bias_before_update()

            disp_bull, disp_bear = self._displacement(i)
            self._manage_levels(i)
            evt_bsl, evt_ssl = self._detect_sweeps(i, disp_bull, disp_bear)

            # Section 13 — detect using the PREVIOUS bar's structure bias
            self._detect_fvg(i, bias_before)
            self._fvg_transitions(i)
            self._fvg_expire(i)

            # Section 14 — market structure break detection
            ms_ev = self.ms.update(i)
            bias = ms_ev.bias

            # Section 14.8 — counter-trend FVG purge on CHoCH
            if ms_ev.choch_bear:
                self.bull_fvg = []
            if ms_ev.choch_bull:
                self.bear_fvg = []

            # Section 13B
            self._ob_update(i)

            # rolling structure-event history
            self._ms_hist.append((i, ms_ev))
            lo_cut = i - cfg.conf_lookback
            self._ms_hist = [(b, e) for (b, e) in self._ms_hist if b > lo_cut - 1]

            # Section 6 / 6B — HTF
            hv = self.htf.step(self.dt.iloc[i], self.l[i], self.h[i], self.c[i], self.atr[i])

            # Section 14.9 — OTE
            oh, ol, o618 = ote_mod.ote_zone(bias, self._ote_rh[i], self._ote_rl[i],
                                            self._ote_ho[i], self._ote_lo[i])
            ote_price_in = np.isfinite(oh) and np.isfinite(ol) and ol <= self.c[i] <= oh
            ote_fvg_ce_in = False
            if np.isfinite(oh) and np.isfinite(ol):
                fvgs = (self.bull_fvg if bias == BULL else
                        self.bear_fvg if bias == BEAR else [])
                for f in fvgs:
                    if f.state in (MITIGATED, DEEP_RETEST):
                        continue
                    if ol <= f.ce <= oh:
                        ote_fvg_ce_in = True
                        break

            active, kz = self._session_flags(self.dt.iloc[i])

            ctx_above = self._prev_day_high is not None and self.c[i] > self._prev_day_high
            ctx_below = self._prev_day_low is not None and self.c[i] < self._prev_day_low

            ob_bull_near = _ob_near(self.ob_bull, self.l[i], "bull")
            ob_bear_near = _ob_near(self.ob_bear, self.h[i], "bear")

            def recent(attr):
                return any(getattr(e, attr) for (b, e) in self._ms_hist if b < i and b >= i - cfg.conf_lookback)

            v = BarView(
                i=i, date=self.dt.iloc[i], close=self.c[i], atr=self.atr[i], bias=bias,
                evt_bsl_swept=evt_bsl, evt_ssl_swept=evt_ssl,
                last_bsl_grade=self.last_bsl_grade, last_ssl_grade=self.last_ssl_grade,
                recent_bsl_sweep=(1 <= i - self.last_bsl_sweep_bar <= cfg.conf_lookback),
                recent_ssl_sweep=(1 <= i - self.last_ssl_sweep_bar <= cfg.conf_lookback),
                recent_bos_bull=recent("bos_bull"), recent_bos_bear=recent("bos_bear"),
                recent_choch_bull=recent("choch_bull"), recent_choch_bear=recent("choch_bear"),
                recent_choch_plus_bull=recent("choch_plus_bull"),
                recent_choch_plus_bear=recent("choch_plus_bear"),
                pdh_swept=(i - self.pdh_swept_bar) <= 20,
                pdl_swept=(i - self.pdl_swept_bar) <= 20,
                indu_bsl=self.indu_bsl_count >= 2,
                indu_ssl=self.indu_ssl_count >= 2,
                kill_zone=kz, active_session=active,
                ctx_above=bool(ctx_above), ctx_below=bool(ctx_below),
                ote_price_in_zone=bool(ote_price_in), ote_fvg_ce_in=ote_fvg_ce_in,
                ob_bull_near=ob_bull_near, ob_bear_near=ob_bear_near,
                htf=hv,
                bull_fvgs=[f for f in self.bull_fvg],
                bear_fvgs=[f for f in self.bear_fvg],
                ssl_levels=[(x.price, x.swept) for x in self.ssl],
                bsl_levels=[(x.price, x.swept) for x in self.bsl],
            )
            views.append(v)
        return views


def _lv_price_of_last(levels):
    for lv in reversed(levels):
        if lv.swept:
            return lv.price
    return float("nan")


def _ob_near(obs, px, side):
    for ob in obs:
        if ob.state == MITIGATED:
            continue
        rng = ob.top - ob.bot
        if side == "bull" and ob.bot - rng * 0.5 <= px <= ob.top + rng * 0.5:
            return True
        if side == "bear" and ob.bot - rng * 0.5 <= px <= ob.top + rng * 0.5:
            return True
    return False


# legacy alias kept for callers importing from engine
lv_price_of_last = _lv_price_of_last
