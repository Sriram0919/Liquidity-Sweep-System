# LSS News Monitor — Indian Equity Coverage Update

## What Was Fixed

The news monitor was missing Indian equity stock news (e.g. Tejas Networks ₹1,537 cr order win on 27 Aug 2026) because `INDIA_KEYWORDS` only had macro/index-level keywords and no corporate event terms.

---

## Changes Made

### 1. `config.py` — Added Corporate Event Keywords

Added to `INDIA_KEYWORDS`:

```python
# ── Corporate Events ─────────────────────────────────────────
"order win", "wins order", "order received", "secures order",
"order book", "contract win", "contract awarded",
"quarterly results", "Q1 results", "Q2 results", "Q3 results", "Q4 results",
"net profit", "PAT", "revenue growth", "EBITDA",
"upper circuit", "lower circuit",
"acquisition", "merger", "takeover", "stake sale",
"demerger", "rights issue", "buyback",
"block deal", "bulk deal",
"rating upgrade", "rating downgrade",
```

### 2. `news_monitor.py` — Added RSS Feeds

Added to `INDIA_RSS_FEEDS`:

```python
# Business Standard Markets
"https://www.business-standard.com/rss/markets-106.rss",
# Google News — India stocks corporate news
"https://news.google.com/rss/search?q=India+stock+order+win+results+circuit&hl=en-IN&gl=IN&ceid=IN:en",
```

---

## How It Works Now

- Monitor runs every **10 minutes** via GitHub Actions (free, always on)
- Scans 10 RSS feeds for India including ET Markets, Moneycontrol, LiveMint, Business Standard
- Keywords are **event-type based** — catches any Nifty 500 stock, not just specific companies
- Alerts sent to Telegram within 10 minutes of a headline going live

## Coverage

| Event Type | Example |
|---|---|
| Order wins | "Tejas Networks secures ₹1,537 cr order from TCS" |
| Results | "Infosys Q2 results — net profit up 12%" |
| Circuit | "Suzlon hits upper circuit after order win" |
| M&A | "Adani acquires stake in XYZ Ltd" |
| Block deals | "Promoter sells 5% via block deal" |
| Rating changes | "ICRA upgrades rating of ABC Corp" |

---

## Commits

- `c5b6f37` — feat: add corporate event keywords to INDIA_KEYWORDS
- `b30fc5f` — feat: add Business Standard and Google News corporate RSS feeds
