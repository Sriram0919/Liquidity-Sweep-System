# News calendar patch — compile/replay required

This patch updates only the active LSS-Pro.pine source. Historical version files are preserved.

- EIA/API windows use America/New_York rather than fixed UTC offsets.
- Published 2026 holiday dates are included. For example API moves to Sep 9 at 16:30 ET and EIA Crude to Sep 10 at 12:00 ET.
- Automatic calendars are explicitly limited to 2026. Custom-release and manual inputs cover other verified events; the chart reports an unverified schedule outside that year.
- News blocking covers all entry paths: new signal setup, pending activation and FVG retest. Because those paths use OHLC[1], the prior bar's news gate is also respected.
- Pre-positioning captures/confirms only on closed bars, respects the news-filter switch and disarms after the event. The existing once-per-event latch and per-bar score reset are preserved.
- The existing dashboard news row shows a countdown using the same release timestamp as the gates. It updates when the chart updates, not from a separate wall-clock timer.

The active source already disabled the invented Nifty weekly window and fixed the broken trend-alert placeholder; those were not reintroduced. No RSS-to-Pine input bridge is claimed.

## Required TradingView verification before use

No Pine compiler is available locally. Compile this source in TradingView, then replay 1m, 5m and 15m charts:

1. MCX Crude/CL: normal summer Wed release, winter Wed release, and Sep 9–10 2026 holiday shift.
2. API Sep 8–9 2026: no Tue false event, Wed 16:30 ET event.
3. NG: Nov 12–13 and Nov 25–26 2026 holiday shifts.
4. Nifty/equity/gold: no commodity automatic gate; explicit manual/custom mode works.
5. Pending CE touch and FVG retest during/just after news remain blocked. Invalidation and expiry continue while blocked.
6. News/pre-positioning switches off: no +8 bonus or pre-positioning alert. One confirmation per event on a closed bar.
7. Custom-release mode supersedes automatic events and stops after its post window; disable it to resume the calendar.
8. 2027 chart: automatic schedule is marked unverified; use manual/custom until calendars are updated.

## Primary references (verified 2026-09-09)

- https://www.eia.gov/petroleum/supply/weekly/schedule.php
- https://ir.eia.gov/ngs/schedule.html
- https://www.api.org/energy-insights/statistics/wsb
- https://www.api.org/-/media/Files/Publications/WSB%20Schedule%20of%20Releases%202026.pdf
- https://www.tradingview.com/pine-script-docs/concepts/time/
