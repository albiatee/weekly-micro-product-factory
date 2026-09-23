# Phase 3 — Opportunity Engine

## Purpose

Turn **stored Signals** into **hypothesized Opportunities** that conform to the Phase 1 Opportunity contract.

**Opportunity score ≠ market validation.**  
Signals are evidence/input, not proof of commercial demand.

## Architecture

```
data/signals/index.json
        ↓
select signal ids (all or explicit)
        ↓
build_opportunity_from_signals (deterministic)
        ↓
contracts.validate_opportunity
        ↓
basic dedupe
        ↓
data/opportunities/index.json
```

Initial status is always **`hypothesized`**.  
Phase 3 never moves opportunities to `experimenting`, `decided`, `building`, `shipped`, or `killed`.

## Signal → Opportunity

- Every hypothesized Opportunity includes `signal_ids` of **existing** Signals.
- Missing signal references → reject (no silent invent).
- Default: **one Opportunity per Signal**.
- `--combine`: one Opportunity from multiple Signals together.

## Generation logic

| Field | Source |
|-------|--------|
| title / problem | From signal `raw_text` (truncated / combined) |
| audience | Extracted only if explicit “for …” pattern; else `unspecified (not stated…)` |
| value_proposition / hypothesis | Marked `[HYPOTHESIS]` — provisional |
| solution_type | Keyword heuristic → allowed enum (default `unknown`) |
| geo | From `geo_hint` / `language` only; else `unknown` + honest rationale |
| score | Deterministic heuristics 0–100 (priority rank, not proof) |

**Does not invent:** market size, revenue, conversion rates, validated willingness to pay, competitor weakness as fact.

## Scoring methodology

Dimensions: intensity, willingness_to_pay, reachability, competition_gap, feasibility, ethics, total.

- Based on signal count, explicit pay-related words, known language/geo, solution_type feasibility map, ethics keyword filters.
- Conservative when evidence is thin.
- **For prioritization only.**

## Deduplication

- Same sorted `signal_ids` set, or same normalized problem text.
- Not semantic AI clustering.
- When uncertain, keep separate.
- Does not overwrite existing opportunities; reports **duplicate**.

## Storage

`data/opportunities/index.json` — separate from `data/signals/` and `catalog/index.json`.

## CLI

```bash
# All stored signals → one opportunity each
python scripts/generate_opportunities.py

# Specific signals
python scripts/generate_opportunities.py --signal-id sig_xxx --signal-id sig_yyy

# Combine into one opportunity
python scripts/generate_opportunities.py --signal-id sig_xxx --signal-id sig_yyy --combine

# Validate without writing
python scripts/generate_opportunities.py --dry-run
```

## What Phase 3 does NOT do

- Experiments / measurement
- Decisions (`execute` / `iterate` / `kill`)
- Production / weekly-build
- Distribution, analytics, LearningRecord engine
- LLM commercial decisions
- Network / paid APIs
