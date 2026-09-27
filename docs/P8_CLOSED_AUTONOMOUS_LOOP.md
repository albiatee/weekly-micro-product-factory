# P8 — Closed Autonomous Loop v0.1

## Goal

Close the factory loop under **Policy + Guardrails + Kill Switch**:

```text
Signal → Quality → Opportunity → Experiment → Decision
  → Build (if execute) → Analytics → Learning → Knowledge feedback
```

## State machine

`created → discovering → opportunity → experimenting → deciding
 → building → measuring → learning → completed`

Terminal: `failed`, `killed`

**Illegal:** `experimenting → building` (must pass `deciding` + `execute`).

## Decision gate

Before build:

- `Decision.verdict == execute` (or dry-run projected verdict)
- Opportunity status appropriate (`building` after execute)
- Guardrails `check_produce_path`
- Template whitelist `static_html_microproduct`
- Experiment completed with predeclared criteria

## Kill switch

If `ORCHESTRATOR_ENABLED` is false and not dry-run / force_enabled:

- state=`killed`, no build, no publish

## LLM role

May propose; **must not** invent evidence/metrics, change thresholds, or execute build/publish.

## CLI

```bash
python scripts/run_factory.py --dry-run
python scripts/run_factory.py --live --force-enabled --opportunity-id opp_... --metrics-json '{"signups":10}'
```

## API

`POST /cycles/run` `{ "dry_run": true }` — local only, `live_publish: false`

## Limitations

- No public publishing
- Metrics must be supplied for full measure/learn after build
- Network signal collect remains off by default


## Idempotency

Pass the same `cycle_id` to `run_closed_loop`. If that cycle is already terminal (`completed`/`failed`/`killed`), the stored record is returned with `idempotent_replay: true` and **no** new experiment/decision/build/analytics/learning is written.
