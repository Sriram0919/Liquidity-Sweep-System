"""Section 14 — Market Structure Engine (BOS / CHoCH / CHoCH+).

Full port of LSS-Pro.pine Section 14 (v2.3.0), replacing the PoC swing-proxy
in structure.py. Runs bar-by-bar; detection uses confirmed bar[1] / bar[2]
offsets so there is no repaint.

Outputs per bar (mirroring the Pine event vars consumed by Section 15/16):
    bias                         STRUCTURE_BIAS  ("Bull" / "Bear" / "—")
    evt_bos_bull / evt_bos_bear
    evt_choch_bull / evt_choch_bear
    evt_choch_plus_bull / evt_choch_plus_bear
    last_sh / last_sl            current tracked structure swings (for OTE etc.)

Pine ordering note: Section 13 (FVG) runs BEFORE Section 14 each bar, so the
FVG structure-alignment filter sees STRUCTURE_BIAS as of the *previous* bar.
The engine calls `bias_before_update()` for that, then `update()`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import indicators as ind

BULL, BEAR, NONE = "Bull", "Bear", "—"


@dataclass
class MSEvents:
    bias: str = NONE
    bos_bull: bool = False
    bos_bear: bool = False
    choch_bull: bool = False
    choch_bear: bool = False
    choch_plus_bull: bool = False
    choch_plus_bear: bool = False
    last_sh: float = float("nan")
    last_sl: float = float("nan")


class MarketStructure:
    def __init__(self, df, cfg):
        self.cfg = cfg
        lb = cfg.ms_swing_lb
        self.o = df["open"].to_numpy(float)
        self.h = df["high"].to_numpy(float)
        self.l = df["low"].to_numpy(float)
        self.c = df["close"].to_numpy(float)
        self.v = df["volume"].to_numpy(float)
        self.piv_h = ind.pivot_high(df["high"], lb, lb).to_numpy(float)
        self.piv_l = ind.pivot_low(df["low"], lb, lb).to_numpy(float)
        self.vol_sma = ind.sma(df["volume"], cfg.vol_len).to_numpy(float)

        self.bias = NONE
        self.last_sh = np.nan
        self.last_sh_bar = -1
        self.last_sl = np.nan
        self.last_sl_bar = -1

    def bias_before_update(self) -> str:
        return self.bias

    def _off(self, arr, i, k):
        j = i - k
        return arr[j] if j >= 0 else np.nan

    def update(self, i) -> MSEvents:
        cfg = self.cfg
        lb = cfg.ms_swing_lb
        ev = MSEvents(bias=self.bias)

        # ── 14.1 register newly-confirmed structure swings ──────
        sh = self.piv_h[i]
        sl = self.piv_l[i]
        if np.isfinite(sh):
            self.last_sh = sh
            self.last_sh_bar = i - lb
        if np.isfinite(sl):
            self.last_sl = sl
            self.last_sl_bar = i - lb

        h1, l1, c1, o1 = (self._off(a, i, 1) for a in (self.h, self.l, self.c, self.o))
        vsma = self.vol_sma[i]
        v1 = self._off(self.v, i, 1)

        # ── 14.5 bullish structure break ───────────────────────
        if np.isfinite(self.last_sh) and np.isfinite(h1) and h1 > self.last_sh and c1 > self.last_sh:
            is_choch = self.bias in (BEAR, NONE)
            body1 = abs(c1 - o1)
            range1 = h1 - l1
            disp = (is_choch and range1 > 0 and body1 / range1 >= cfg.choch_disp_pct
                    and np.isfinite(vsma) and v1 > vsma * cfg.vol_mult)
            self.bias = BULL
            if disp:
                ev.choch_plus_bull = True
                ev.choch_bull = True
            elif is_choch:
                ev.choch_bull = True
            else:
                ev.bos_bull = True
            self.last_sh = np.nan
            self.last_sh_bar = -1

        # ── 14.6 bearish structure break ───────────────────────
        if np.isfinite(self.last_sl) and np.isfinite(l1) and l1 < self.last_sl and c1 < self.last_sl:
            is_choch = self.bias in (BULL, NONE)
            body2 = abs(c1 - o1)
            range2 = h1 - l1
            disp2 = (is_choch and range2 > 0 and body2 / range2 >= cfg.choch_disp_pct
                     and np.isfinite(vsma) and v1 > vsma * cfg.vol_mult)
            self.bias = BEAR
            if disp2:
                ev.choch_plus_bear = True
                ev.choch_bear = True
            elif is_choch:
                ev.choch_bear = True
            else:
                ev.bos_bear = True
            self.last_sl = np.nan
            self.last_sl_bar = -1

        ev.bias = self.bias
        ev.last_sh = self.last_sh
        ev.last_sl = self.last_sl
        return ev
