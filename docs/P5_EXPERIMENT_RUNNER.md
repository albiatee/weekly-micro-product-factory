# P5 — Experiment Runner v0.1

## Purpose

Run a **limited real experiment** from an evidence-ready Opportunity:

```text
Opportunity
  → Experiment Spec (predeclared success/failure criteria)
  → start
  → local artifact (smoke HTML) + metrics input
  → completed
  → Policy evaluation (advisory only)
```

## What is "real" in v0.1

- Creates a **local HTML artifact** under `data/experiment_runs/<exp_id>/` (not GitHub Pages publish)
- Requires **explicit metrics** (caller JSON or `metrics.json`) — never invents signups
- Completes lifecycle via existing experiment engine
- Calls **Policy.evaluate** for advisory verdict only

## What it refuses

- Public publish / Path A product generation
- Bypassing Policy or Guardrails
- Auto `execute` → build
- Types outside `smoke_page`, `waitlist`, `manual_pilot`

## CLI

```bash
python scripts/run_experiment.py run --opportunity-id opp_... --metrics-json '{"signups":7}'
python scripts/run_experiment.py run --opportunity-id opp_...   # starts + artifact; left running
python scripts/run_experiment.py complete --experiment-id exp_... --metrics-json '{"signups":2}'
```

## API

```http
POST /experiments/run
POST /experiments/complete
```

Both set `live_publish: false`.

## Safety

Policy / Guardrails remain authoritative. Runner does not open kill switch or whitelist publish.
