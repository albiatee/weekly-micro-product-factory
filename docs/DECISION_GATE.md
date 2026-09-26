# Decision Gate (Phase 5)

## Purpose

Convert **completed Experiment** evidence into an auditable Decision:

`execute` | `iterate` | `kill`

**Decision outcome is not equivalent to market truth.**  
**Execute does not automatically create or deploy a product.**  
**Iterate does not automatically launch another experiment.**

Phase 6+ owns downstream execution.

## Layer separation

```text
Signal Quality ≠ Opportunity Evidence ≠ Experiment Results ≠ Decision
```

## Prerequisites

- Opportunity status = `experimenting`
- `experiment_id` **required** (specific experiment — not “latest”)
- Experiment status = `completed`
- Results/observations present
- Predefined `measurement_plan`, `success_criteria`, `failure_criteria` on the experiment
- Rationale ≥ 20 characters explaining evidence vs criteria
- Valid `evidence_refs` including the experiment id

## Decision model (key fields)

| Field | Role |
|-------|------|
| `verdict` / `decision` | execute \| iterate \| kill |
| `reason` / `rationale` | Human explanation |
| `experiment_id` | Experiment evaluated |
| `opportunity_id` | Parent opportunity |
| `evidence_refs` | exp_/sig_ refs |
| `criteria_snapshot` | Frozen pre-result criteria from experiment |
| `metrics_snapshot` | Observed results/observations |
| `evidence_summary` | Short audit string |
| `assumptions_affected` | From experiment.assumptions_tested |
| `next_action` | Guidance only (not auto-run) |
| `decided_by` | human \| human_with_agent_suggestion |
| `decided_at` | Timestamp |

## Evaluation mode

**Manual / explicit verdict.** The gate does **not** invent numeric thresholds or auto-map metrics → verdict when criteria are free-form. Humans supply `verdict` + rationale; the system enforces structure, completion, and snapshots.

`agent_suggestion` never overrides human `verdict`.

## Opportunity status after decision

| Verdict | Opportunity status (existing path) |
|---------|-------------------------------------|
| execute | `building` (production is Phase 6) |
| iterate | `iterating` |
| kill | `killed` |

## Duplicates

- One finalized Decision per **experiment**
- Opportunity `latest_decision_id` blocks silent second decision
- New evidence cycle → new experiment → new decision

## Traceability

```text
Decision → experiment_id → Experiment → opportunity_id → Opportunity → signal_ids → Signals
         → criteria_snapshot (predefined)
         → metrics_snapshot (observed)
```

## CLI

```bash
python scripts/manage_decisions.py create \
  --opportunity-id opp_... \
  --experiment-id exp_... \
  --verdict execute|iterate|kill \
  --reason "..." \
  --evidence-ref exp_... \
  --decided-by human \
  [--next-action "..."]

python scripts/manage_decisions.py list
python scripts/manage_decisions.py inspect --decision-id dec_...
```

## Limitations

- No automatic scoring of free-form criteria text
- No multi-experiment aggregation in one decision
- Status `building` does not build a product by itself
