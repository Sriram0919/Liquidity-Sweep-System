# LSS News Monitor — Change Log

Companion repo: `Sriram0919/lss-news-monitor` (private, GitHub Actions + RSS + Telegram).
This file tracks changes made to it from the LSS project.

---

## 2026-09-04 — India/commodity coverage rebuild (PR #1, branch `fix/india-coverage`)

**Problem:** barely any Indian stock news was coming through. Review found the
causes were structural, not missing keywords.

| # | Root cause | Fix |
|---|---|---|
| 1 | `RSS_LOOKBACK_MINUTES = 30` but GitHub throttles the `*/10` cron to ~3–5 h gaps on a private repo → ~90% of the timeline never scanned | **State-driven window** — `state.json` (last-run watermark + seen ids), committed back each run; scan since last run − overlap, capped at `MAX_LOOKBACK_MIN` |
| 2 | Google News *search* feeds are relevance-sorted (newest items 700–900 h deep) and were the only feeds with single-stock news → 30-min filter killed all of it | Scope GN feeds with `when:`; add chronological publisher feeds (ET Markets/Stocks/Economy, BS Markets/Companies, Mint Markets/Companies) |
| 3 | Dead feeds: Reuters RSS (retired), Moneycontrol (frozen ~2 yr) | Removed; added Oilprice.com |
| 4 | Substring keyword matching — `PAT`→"compatible", `SPR`/`EIA` false hits | Whole-word regex matching |
| 5 | `seen_urls` in-memory only (empty every Actions run) | Persisted in `state.json` (`SEEN_CACHE_SIZE` ids) |
| 6 | A multi-hour gap would now dump 100+ matches to Telegram at once | **Two keyword tiers** — `*_KEYWORDS_HIGH` (events/surprises) → individual alerts, capped `MAX_ALERTS_PER_RUN=8`; `*_KEYWORDS_CONTEXT` (index chatter) + overflow → one digest message |
| 7 | Investing.com dates unparseable (→ every item treated "recent"); Atom `<link>` href ignored | Added date format; read `<link href>`; GN source = publisher name |

Workflow: added `permissions: contents: write`, `concurrency` guard, and a
persist-state commit step.

**Latency decision (stays on GitHub Actions):** the state window makes throttle
gaps non-fatal, so no always-on host — keeps it zero-cost / zero-maintenance,
which is what a discretionary pre-positioning aid needs. Instead: cron moved
`*/10` → `4,19,34,49 * * * *` (every 15 min, off the `:00`/`:30` marks GitHub
throttles hardest); alerts now show headline age (`· 2h ago`) so a stale hit is
obvious; scheduled macro events (EIA/CPI/RBI) ride `calendar_monitor`, which
polls every run regardless.

**Verified locally** against live feeds: 20-min window → 8 hits; immediate
re-run → 0 (dedup); simulated 6 h gap → 169 raw matches collapsed to 8 alerts
+ 1 digest; `py_compile` clean. Not verified: live Telegram send, the
workflow's git-push-back (first runs on merge).

**Open:** GitHub Actions can't do a true 10-min schedule on a private repo —
move `monitor.py` to an always-on host if sub-hour latency is needed.

---

## 2026-08-28 — Indian equity keywords + feeds (commits c5b6f37, b30fc5f)

`INDIA_KEYWORDS` had only macro/index terms — no corporate-event wording, so
single-stock catalysts (e.g. Tejas Networks order win, 27 Aug) were missed.
Added order-win / results / circuit / M&A / block-deal / rating keywords, plus
Business Standard Markets and a Google News corporate-news feed. (Superseded
by the 2026-09-04 rebuild — keyword list restructured into tiers.)
