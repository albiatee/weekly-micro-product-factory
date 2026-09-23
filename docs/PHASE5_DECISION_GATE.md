# Phase 5 — Decision Gate

## Purpose

Turn **completed Experiment evidence** into an **explicit Decision** on an Opportunity.

```
experimenting + Experiment completed
        ↓
Decision (execute | iterate | kill)
        ↓
building | iterating | killed
```

**Decision ≠ Experiment.** Experiments measure; Decisions interpret evidence.

`passed=true` alone does **not** create a Decision or prove market certainty.

## Contract (Phase 1)

Required: `id` (`dec_...`), `opportunity_id`, `verdict`, `reason`, `evidence_refs`, `decided_by`, `decided_at`  

Optional: `experiment_id`, `agent_suggestion`  

`evidence_refs`: only `exp_...` / `sig_...` that **exist** and (for exp) belong to the same Opportunity.

## Verdicts

| verdict | Opportunity outcome | Meaning |
|---------|---------------------|---------|
| execute | building | Evidence enough to **attempt** build path — not guaranteed success |
| iterate | iterating | Revise hypothesis/solution/experiment |
| kill | killed | Stop this path (terminal) |

Path enforced: `experimenting → decided → outcome` (validated); stored status is the outcome with `latest_decision_id` set.

## Rules

- Opportunity must be **`experimenting`**
- At least one **completed** Experiment for this Opportunity in evidence
- **Aborted/running** experiments are not enough for a Decision
- No silent second Decision if `latest_decision_id` already set
- `agent_suggestion` is optional advice; **never** overrides `verdict`
- **No Production trigger** — `building` is a state only; Phase 6 would implement production

## CLI

```bash
python scripts/manage_decisions.py create \
  --opportunity-id opp_xxx \
  --verdict execute \
  --reason "Completed waitlist experiment met agreed criterion; proceeding to build phase" \
  --evidence-ref exp_xxx \
  --experiment-id exp_xxx \
  --decided-by human

python scripts/manage_decisions.py list
```

`--dry-run` validates without writing decisions or updating opportunities.

## Storage

`data/decisions/index.json`

## What Phase 5 does NOT do

- Production / weekly-build
- Distribution, Analytics, Learning
- Automatic winner from score / threshold / passed
- Fabricated market claims in `reason`
