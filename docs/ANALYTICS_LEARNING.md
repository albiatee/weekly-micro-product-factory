# Analytics & Learning (Phase 8)

## Purpose

Observe the V2 lifecycle and optionally write **snapshots** and **LearningRecords**.

**Observational only.** Does not change Signal / Opportunity / Experiment / Decision / Production / Distribution status.

## Analytics metrics

Record counts (not forced unique joins):

- signals total + by qualification / intent
- opportunities + evidence-ready count
- experiments by status
- decisions by execute / iterate / kill
- production specs by status
- distribution plans by status + publication success/fail/not-recorded

Rates are `null` when the denominator is zero (not `0`).

## Funnel semantics

Stages are **independent record counts**. Drop-off is not always causal.

## LearningRecord

Contract fields: `id`, `opportunity_id`, `what_worked`, `what_failed`, `created_at`, optional experiment/decision ids.

Phase 8 also stores: `observation`, `interpretation`, `learning`, `confidence`, `source_ids`, `assumptions`, `unknowns`.

Does **not** invent market demand or channel causality.

## Idempotency

- Snapshot: one stored snapshot per filter key (latest wins).
- Learning: one record per `opportunity_id` (stable id on re-run).

## CLI

```bash
python scripts/run_analytics.py summary
python scripts/run_analytics.py funnel
python scripts/run_analytics.py inspect
python scripts/run_analytics.py learn
python scripts/run_analytics.py learning-inspect --learning-id lr_...
```

## Phase 9 boundary

No discovery feedback, human-review workflow, or automatic new Signals from learning.
