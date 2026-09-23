# Phase 2 extension — Web RSS/Atom Signal Collector

## Purpose

Collect **public RSS/Atom** items into **Signals** using the existing Phase 2 path:

```text
RSS/Atom HTTP GET → RawSignalCandidate → normalize → validate → dedupe → store
```

Does **not** create Opportunities, Experiments, or Decisions.  
Does **not** prove market demand. Feed text is observation only.

## Architecture

| Piece | Role |
|-------|------|
| `discovery/sources/web_rss.py` | Fetch + parse + map to `RawSignalCandidate` |
| `config/signal_sources.json` | Configurable feed list |
| `scripts/collect_web_signals.py` | CLI |
| Phase 2 pipeline | `ingest_candidates` / `process_candidate` |

## Supported formats

- RSS 2.0 (`<item>`)
- Atom (`<entry>`)

No HTML scraping, no JavaScript, no browser automation.

## Configuration

`config/signal_sources.json`:

```json
{
  "feeds": [
    {
      "name": "hnrss_frontpage",
      "url": "https://hnrss.org/frontpage",
      "source": "other"
    }
  ]
}
```

- `source` must be a Signal contract value or use `"other"` with name in `meta.source_detail`.

## CLI

```bash
python scripts/collect_web_signals.py --dry-run --limit 10
python scripts/collect_web_signals.py --source hnrss_ask --limit 5
python scripts/collect_web_signals.py --timeout 20
```

`--dry-run`: fetch and validate; **no** writes to `data/signals/`.

## Network safety

- HTTPS/HTTP only
- Timeout (default 15s)
- Max body size (2MB)
- Clear User-Agent
- Per-feed error isolation (one failed feed does not stop others)
- No credentials / API keys

## Provenance

```json
"meta": {
  "source_detail": "<feed name>",
  "collector": "rss",
  "title": "..."
}
```

## Deduplication

Reuses Phase 2 `find_duplicate` (normalized text / URL). Second run on same feed should yield duplicates, not new rows.

## Limitations

- Feed quality varies; short/empty items are rejected
- Default feeds (HN RSS) are general tech discussion — not niche market proof
- No semantic clustering or LLM filtering
- Sites may rate-limit or block; treat as best-effort


## Configured feeds (specialized prioritization)

| Name | URL | Category | Notes |
|------|-----|----------|-------|
| hnrss_ask | https://hnrss.org/ask | Software / questions | Ask HN — problems & requests |
| hnrss_show | https://hnrss.org/show | Software / builders | Show HN — tools & gaps |
| hnrss_q_saas | https://hnrss.org/newest?q=SaaS | SaaS | Keyword filter |
| hnrss_q_invoice | https://hnrss.org/newest?q=invoice | Small business ops | Keyword filter |
| hnrss_q_freelance | https://hnrss.org/newest?q=freelance | Freelance | Keyword filter |
| lobsters | https://lobste.rs/rss | Developer community | Technical discussions |
| hnrss_frontpage | https://hnrss.org/frontpage | Exploratory | High noise; keep for coverage |
| hnrss_newest | https://hnrss.org/newest | Exploratory | Firehose; high noise |

**Rejected at config time:** ihrss.io (returns HTML not RSS), Product Hunt feed (mostly launches not problems), Stack Overflow Blog (editorial news), Algeria/MENA general news feeds (no verified problem-oriented public RSS without login/API).

Feed text ≠ proven demand. Human review remains required before Opportunity.
