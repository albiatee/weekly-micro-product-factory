# P0 — Control Plane Design Lock

**Date:** 2026-09-26  
**Status:** Contracts only — **no Orchestrator code**

## Deliverables

| Document | Role |
|----------|------|
| [`AUTONOMOUS_POLICY_V0.md`](AUTONOMOUS_POLICY_V0.md) | Policy v0.1.0 — authorization rules |
| [`ORCHESTRATOR_CONTRACT_V0.md`](ORCHESTRATOR_CONTRACT_V0.md) | Cycle sequence, states, SELECT, guardrail order |
| [`OPERATING_RULES.md`](OPERATING_RULES.md) §14 | Operating pointer |

## Architecture split

| Layer | Responsibility |
|-------|----------------|
| Orchestrator | What to run and when |
| Policy | Whether the next step is allowed |
| Guardrails | What cannot be exceeded even if Policy says yes |

## Confirmed non-goals (P0)

No Orchestrator implementation, no scheduler, no live experiment, no publish, no Path A changes, no removal of human gates, no autonomy claim from docs alone.

## Next (after human acceptance of contracts)

**P1:** Orchestrator **dry-run** (COLLECT→…→DECIDE log only; no PRODUCE/BUILD/PUBLISH).
