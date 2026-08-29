"""Simplified market-structure bias for the PoC.

Pine's Section 14 runs a full BOS / CHoCH / CHoCH+ state machine. That is out
of scope for the proof-of-concept (Backtest-Bench-Plan.md step 3 = "sweep +
FVG + scoring core"). Here we derive a 3-state bias purely from confirmed
swing pivots:

    BULL  : higher-high AND higher-low  vs the previous confirmed pair
    BEAR  : lower-low  AND lower-high
    NONE  : mixed / not enough pivots

This is a KNOWN DIVERGENCE from the live indicator and is flagged in the
run report. Porting Section 14 is step 4 of the plan.
"""
from __future__ import annotations

BULL, BEAR, NONE = "Bull", "Bear", "—"


class StructureBias:
    def __init__(self) -> None:
        self.highs: list[float] = []
        self.lows: list[float] = []
        self.bias: str = NONE

    def update(self, confirmed_high: float | None, confirmed_low: float | None) -> str:
        if confirmed_high is not None:
            self.highs.append(confirmed_high)
            self.highs = self.highs[-3:]
        if confirmed_low is not None:
            self.lows.append(confirmed_low)
            self.lows = self.lows[-3:]

        if len(self.highs) >= 2 and len(self.lows) >= 2:
            hh = self.highs[-1] > self.highs[-2]
            hl = self.lows[-1] > self.lows[-2]
            ll = self.lows[-1] < self.lows[-2]
            lh = self.highs[-1] < self.highs[-2]
            if hh and hl:
                self.bias = BULL
            elif ll and lh:
                self.bias = BEAR
            else:
                self.bias = NONE
        return self.bias
