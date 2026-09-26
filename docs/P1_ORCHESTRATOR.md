# P1 — Orchestrator Dry-Run (implemented)

**Status:** Control plane **code** landed; autonomy **not** enabled by default.

## Packages

| Package | Role |
|---------|------|
| `orchestrator/` | Cycle sequencing, store, kill switch, runner |
| `policy/` | Deterministic evaluate + SELECT ranking |
| `guardrails/` | Hard ceilings (dry_run, whitelist, publish caps) |
| `config/orchestrator_v0.json` | Limits + allowlists (`orchestrator_enabled: false`) |

## CLI

```bash
python scripts/run_orchestrator_cycle.py --dry-run --stop-after SELECT
python scripts/run_orchestrator_cycle.py --dry-run --stop-after DECIDE
```

Dry-run always allowed for inspection. Live (non-dry) requires `ORCHESTRATOR_ENABLED=true` **and** `--live`.

## Behaviour v0

- Fixed step order; no jumps
- COLLECT: skipped unless `collect_on_cycle` (default false — no surprise network)
- QUALIFY → OPPORTUNITY → SELECT on existing stores
- EXPERIMENT: attaches **existing completed** experiments only (no auto-start live experiments)
- DECIDE: Policy evaluation; may write Decision with `decided_by=policy:policy_autonomous_factory_v0`
- PRODUCE/BUILD/PUBLISH/MEASURE/LEARN/FEEDBACK: logged as skipped under dry-run / not fully automated in v0

## Tests

`tests/test_orchestrator_policy.py` — steps, kill switch, policy table, select, guardrails, dry-run cycle.

## Not done (later)

- Auto-start experiments with synthetic/operator metrics
- Real BUILD + github_pages PUBLISH
- Scheduler/cron
- Enabling `orchestrator_enabled` by default
