# Signal Quality Layer (Phase 2)

## Why it matters

V2 can ingest many Signals. Without quality rules, **Supply / Promotion / Noise** enter Opportunity generation and poison the loop.

This layer answers: **Should this signal enter Opportunity Discovery?**

It does **not** prove market demand. Qualification ≠ validation.

## Taxonomy (`intent_type`)

| Intent | Side | Meaning |
|--------|------|---------|
| `problem` | demand | Concrete pain described |
| `question` | demand | Seeking how to solve something |
| `request` | demand | Asks for a tool/way/solution |
| `complaint` | demand | Strong negative experience |
| `buying_intent` | demand | Willingness to pay / replace paid tool |
| `workaround` | demand | Painful manual/substitute process |
| `feature_request` | demand | Missing capability on existing tool |
| `supply` | supply | Offering services / for-hire |
| `promotion` | supply | Launching/marketing a product |
| `news` | info | Podcast/news without problem |
| `noise` | — | Chat, vague, unusable |
| `unknown` | — | No clear pattern |

## Evidence strength

| Strength | Meaning |
|----------|---------|
| `strong` | Specific context + pain/behavior (workaround, cost, time) |
| `medium` | Clear demand-side issue, thinner behavioral evidence |
| `weak` | Vague or thin |
| `invalid` | Supply/promo/news/noise — not demand evidence |

**Not used alone as market truth:** upvotes, comment counts, famous source, RSS presence, keyword hits without context.

## Qualification (`qualification_status`)

| Status | Rule (summary) | Opportunity generation |
|--------|----------------|------------------------|
| `qualified` | Demand-side + strong/medium (core intents) | **Allowed** |
| `review` | Weak demand-side, unknown, borderline | **Blocked** until human promotes |
| `rejected` | Supply / promotion / news / noise / invalid | **Blocked** |

Gate is enforced in `opportunity/pipeline.py` via `is_opportunity_eligible`.

## Source quality model

Configured in `config/signal_sources.json`:

- **`feeds`**: collected by default (`hnrss_ask`, `hnrss_q_invoice`, `hnrss_show`) — **mixed / exploratory**
- **`disabled_feeds`**: frozen (freelance supply-heavy, firehose, frontpage, etc.)

Source type ≠ demand proof. Classification still runs on every item.

## Filtering

- Deterministic patterns in `discovery/quality.py` (no LLM)
- HN boilerplate stripped for analysis (`Points`, `Comments URL`, …)
- Signals still **stored** when contract-valid (audit); opportunity path is gated
- When uncertain → prefer `review` over `rejected`

## Examples

| Text (synthetic) | Expected |
|-------------------|----------|
| “I waste hours every week reconciling invoices manually…” | problem → qualified |
| “Looking for freelance work 300 USD/week DM me” | supply → rejected |
| “Show HN: We built X CRM” | promotion → rejected |
| “145th podcast episode…” | news → rejected |

## What is NOT market validation

- RSS item count
- HN points / comments
- Being `qualified`
- Source reputation
- Keyword match alone

Validation requires experiments + evidence (later phases).

## How to test

```bash
python -m pytest tests/test_signal_quality.py tests/test_signal_discovery.py -q
python -m pytest tests/ -q
```

## Limitations

- Heuristic English-heavy patterns; Arabic/other languages may land in `unknown`/`review`
- Show HN can be both product launch and genuine problem statement — bias toward promotion when “we built” dominates
- Does not replace human judgment for borderline `review` items
