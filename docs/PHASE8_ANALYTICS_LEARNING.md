# Phase 8 — Analytics & Learning

## Purpose

Read existing factory data and produce **deterministic metrics** and **evidence-based LearningRecords**.

```
DATA → METRICS → ANALYSIS → LEARNING RECORDS → (future Discovery hints)
```

**Not:** automatic Decision, score mutation, Signal creation, or product kill/launch.

## Data sources

| Store | Path |
|-------|------|
| Signals | `data/signals/` |
| Opportunities | `data/opportunities/` |
| Experiments | `data/experiments/` |
| Decisions | `data/decisions/` |
| Distribution | `data/distribution/` |

## Metrics (formulas)

| Metric | Formula |
|--------|---------|
| execution_rate | execute decisions / total decisions |
| experiment_completion_rate | completed / (running + completed + aborted) |
| shipping_rate_among_decided | shipped / opportunities with `latest_decision_id` |

Null when denominator is 0. **Never invent metrics.**

Operator-recorded experiment vs distribution results are listed **separately**.  
Votes/signups/clicks ≠ sales or proven demand.

## LearningRecord (Phase 1 contract)

`lr_...` with `opportunity_id`, `what_worked`, `what_failed`, `created_at`, optional `experiment_id`, `decision_id`, `next_signals_hint`, `score_calibration_notes`, `commercial_notes`.

- Evidence-only wording  
- `next_signals_hint` is a **hint** — no Signal is created  
- Score notes do **not** change stored scores  

## CLI

```bash
python scripts/run_analytics.py
python scripts/run_analytics.py --opportunity-id opp_xxx
python scripts/run_analytics.py --learn
python scripts/run_analytics.py --dry-run --learn
```

`--period` reserved (ignored in Phase 8).

## Storage

`data/analytics/index.json` — snapshots + learnings

## Reproducibility

Counts and rates are pure functions of store contents.  
`generated_at` timestamps differ per run; metric values do not (same data).

## Dry-run

No write to analytics store; no changes to Opportunity/Experiment/Decision/Distribution.

## Does NOT do

- Auto execute/iterate/kill  
- Production rewrite  
- External analytics APIs  
- LLM-generated numbers  
- RevenueEvent schema  
