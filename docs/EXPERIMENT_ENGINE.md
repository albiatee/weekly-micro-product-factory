# Experiment Engine (Phase 4)

## Purpose

Make opportunities **testable** with predefined measurement and criteria.

Experiment evidence is **not** automatically market validation.  
**Phase 5** owns Decision Gate (`execute` / `iterate` / `kill`).

## Lifecycle

```text
planned → running → completed
    ↘ aborted     ↘ aborted
```

## Types

`landing_page`, `smoke_page`, `waitlist`, `concierge`, `concierge_manual`,
`prototype`, `interview`, `preorder`, `community_vote`, `manual_pilot`

Execution of the external channel may be manual; the engine tracks definition and evidence.

## Required before start (`is_experiment_ready`)

1. Valid `opportunity_id` + opportunity exists  
2. Opportunity **evidence-ready** (Phase 3)  
3. `hypothesis_test` (clear, ≥ ~20 chars)  
4. `target_population`  
5. Valid `experiment_type`  
6. `measurement_plan`  
7. `success_criteria`  
8. `failure_criteria`  

Optional: `duration`, `observation_window`, `assumptions_tested`, `channel`.

## Immutability

After any `results` / `observations` are recorded, these cannot change:

hypothesis, measurement_plan, success/failure criteria, target_population, type, assumptions_tested.

Create a **new** experiment instead.

## Observations

```json
{
  "metric": "qualified_signups",
  "value": 17,
  "source": "manual_entry",
  "captured_at": "...",
  "notes": "optional"
}
```

`results.passed` is an observational flag only — **not** a business decision.

## Duplicate active experiments

At most **one** `running` experiment per Opportunity.

## Traceability

Experiment → `opportunity_id` → Opportunity → `signal_ids` → Signals → evidence.

## CLI

```bash
python scripts/manage_experiments.py create --opportunity-id opp_... --type waitlist \
  --hypothesis-test "..." --measurement-plan "..." \
  --success-criteria '{"metric":"signups","min":10}' \
  --failure-criteria '{"metric":"signups","below":3}' \
  --target-population "..."

python scripts/manage_experiments.py start --experiment-id exp_...
python scripts/manage_experiments.py results --experiment-id exp_... --metrics-json '{"signups":4}'
python scripts/manage_experiments.py complete --experiment-id exp_...
python scripts/manage_experiments.py inspect --experiment-id exp_...
```

## Limitations

- No automatic traffic generation  
- No auto-decision from metrics  
- Criteria quality depends on the human author  
