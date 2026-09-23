# Phase 2 — Signal Discovery

## Purpose

Collect, normalize, validate, and store **market Signals** as evidence of observations.

Signals are **not** Opportunities. Phase 2 does **not** score markets, design products, or run the weekly factory.

## Flow

```
Manual JSON/JSONL (or future SignalSource)
        → collect candidates
        → normalize (assign sig_ id, trim fields)
        → validate via Phase 1 contracts.validate_signal
        → deterministic dedupe (text/URL fingerprint)
        → store in data/signals/index.json
```

## Supported sources (contract)

`github_issue` | `x` | `reddit` | `trends` | `review` | `competitor` | `manual` | `other`

Phase 2 **implements** manual ingestion only. Other sources plug in via `discovery/sources/` (`SignalSource.collect()`).

## Manual ingestion

```bash
python scripts/ingest_signals.py path/to/signals.json
python scripts/ingest_signals.py path/to/signals.jsonl --dry-run
```

Example payload:

```json
{
  "source": "manual",
  "raw_text": "Users repeatedly complain about complex offline task apps",
  "captured_at": "2026-09-20T12:00:00Z",
  "language": "en",
  "geo_hint": "global"
}
```

Or a list / `{ "signals": [ ... ] }` / JSONL (one object per line).

IDs are generated automatically (`sig_` + hex). Do not invent market size or demand.

## Storage

`data/signals/index.json`

- Git-friendly JSON
- Map of `signal_id → Signal object`
- Preserves source, raw_text, captured_at, optional provenance fields

## Deduplication

Deterministic only:

- Normalize whitespace + lowercase on `raw_text`
- If `url` present, fingerprint by URL
- Exact fingerprint match → **duplicate** (not stored; reported, not silent delete)

Not semantic clustering. `cluster_id` remains optional / unused by default.

## Validation

Reuses Phase 1 `contracts.validate_signal` — no second schema.

## What Phase 2 does NOT do

- Create Opportunities
- Experiments / Decisions
- Production / weekly-build integration
- Distribution, analytics, learning engine
- LLM analysis of signals

## Extending collectors

1. Add `discovery/sources/my_source.py` implementing `SignalSource`
2. Map outputs to `RawSignalCandidate`
3. Call `ingest_candidates(...)` from a script or job later
