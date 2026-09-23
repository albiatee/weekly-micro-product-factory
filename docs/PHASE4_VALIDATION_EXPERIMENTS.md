# Phase 4 — Validation Experiments

## Purpose

Turn a **hypothesized Opportunity** into a **measurable Experiment**, run it, and record **evidence**.

**Phase 4 produces evidence. Phase 5 interprets evidence and creates Decisions.**

Completed experiments do **not** automatically mean “build the product.”

## Architecture

```
Opportunity (hypothesized)
        ↓
create Experiment (planned)
        ↓
start → running (+ Opportunity → experimenting, active_experiment_id)
        ↓
record results (supplied metrics / notes only)
        ↓
complete → completed   OR   abort → aborted
        ↓
READY FOR PHASE 5 DECISION GATE
```

## Lifecycle

| From | To |
|------|-----|
| planned | running, aborted |
| running | completed, aborted |
| completed / aborted | terminal |

Rejected examples: `planned → completed`, `completed → running`.

## Experiment types (contract)

`smoke_page` · `waitlist` · `concierge` · `preorder` · `community_vote` · `manual_pilot`

**`community_vote`** is a supporting preference signal only — **not** full market validation.

## measurement_plan

Required **before/at** `running`: non-empty **string** or non-empty **object**.

## success_threshold

Optional `{ metric, operator, value, window_days }`.  
Passing a threshold = evidence against a criterion, **not** an execute verdict.

## Results

Recorded only from supplied data:

```json
"results": {
  "metrics": { "signups": 3 },
  "qualitative_notes": ["..."],
  "passed": true
}
```

No fabricated metrics, revenue, or LLM demand claims.  
**Cannot complete** without non-empty metrics and/or qualitative_notes.

## Opportunity link

- Every Experiment has `opportunity_id` of an existing Opportunity.
- On **start**: Opportunity `hypothesized → experimenting` and `active_experiment_id = exp_...`.
- On **complete/abort**: Opportunity is **not** auto-`decided` / `killed`.

## Storage

`data/experiments/index.json` — separate from signals, opportunities, catalog, products.

## CLI

```bash
python scripts/manage_experiments.py create --opportunity-id opp_xxx --type waitlist \
  --measurement-plan "Count waitlist signups over 7 days"

python scripts/manage_experiments.py start --experiment-id exp_xxx

python scripts/manage_experiments.py results --experiment-id exp_xxx \
  --metrics-json '{"signups": 5}' --note "Shared in two groups"

python scripts/manage_experiments.py complete --experiment-id exp_xxx

python scripts/manage_experiments.py abort --experiment-id exp_xxx --reason "no traffic"

python scripts/manage_experiments.py list
```

`--dry-run` supported on mutating commands.

## What Phase 4 does NOT do

- Decision records / execute / iterate / kill  
- Production / weekly-build  
- Distribution, analytics engine, learning engine  
- External APIs (Stripe, ads, social)  
- Automatic “winner” ranking  

## Contract reuse

Uses Phase 1 `contracts.validate_experiment` — no second Experiment schema.
