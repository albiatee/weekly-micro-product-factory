# Production Bridge (Phase 6)

## Purpose

Turn an **`execute` Decision** into an auditable **Production Specification**.

`execute` authorizes production **planning/specification**; it does **not** automatically build or deploy a product.  
`iterate` and `kill` **do not** enter the Production Bridge.

## Entry gate (`is_production_ready`)

- Decision exists and `verdict == execute`
- Decision ↔ Opportunity ↔ Experiment IDs consistent
- Experiment **completed**
- Opportunity in `building` (after Decision Gate)

## Production Specification

Key fields: `id` (`prd_…`), `decision_id`, `opportunity_id`, `experiment_id`, problem, target user, solution_type, `core_features`, `non_goals`, `acceptance_criteria`, evidence/criteria/metrics snapshots from Decision, `source_signal_ids`, assumptions (not promoted to facts), `production_status`.

Initial status: **`ready`** (spec ready for work — not deployed).

## Lifecycle (spec entity)

`draft` → `ready` → `in_progress` → `completed`  
(Creation sets `ready`.)

Optional existing path: `scripts/production_bridge.py build` may copy a **digital_micro** template under `products/bridge/` and mark Opportunity `shipped` — still **no** catalog/weekly-build/distribution.

## Idempotency

One Production Specification per finalized **execute** Decision.

## CLI

```bash
python scripts/production_bridge.py spec --decision-id dec_...
python scripts/production_bridge.py list
python scripts/production_bridge.py inspect --production-id prd_...
python scripts/production_bridge.py build --opportunity-id opp_...   # digital_micro only
```

## What Phase 6 does NOT do

Distribution, marketing, hosting, payments, LLM product generation, analytics, discovery feedback.

## Layer boundaries

Decision ≠ Production Specification ≠ Deployment ≠ Distribution
