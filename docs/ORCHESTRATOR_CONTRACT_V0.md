# Orchestrator Contract v0

**Status:** P0 contract — locked for design; **not** implemented in code.  
**Control plane role:** *What* to run and *when* (ordered steps + cycle state).  
**Does not authorize:** Authorization is **Policy** + **Guardrails** only.

> Human gates in Phases 1–11 remain valid for legacy/manual mode.  
> This contract describes the **future** autonomous loop. Shipping this file does **not** make the factory autonomous.

---

## 1. Layering (authoritative order)

```text
System Kill Switch
       ↓
Hard Guardrails
       ↓
Policy (authorization)
       ↓
Orchestrator (this contract — sequencing)
       ↓
Existing Phase 1–11 pipelines (execution backends)
       ↓
LLM / Agents (optional assist; never authorize)
```

| Component | Question it answers |
|-----------|---------------------|
| Orchestrator | What step runs now? What is the cycle state? |
| Policy | Is the transition allowed? |
| Guardrails | Is the action blocked regardless of Policy? |

Orchestrator **must not** become a monolithic rules engine. It calls Policy for authorization checks and aborts when Guardrails fire.

---

## 2. Cycle identity and states

### Identity

```text
cycle_id: cyc_<id>
policy_id: policy_autonomous_factory_v0
policy_version: 0.1.0
```

### States

| State | Meaning |
|-------|---------|
| `running` | Steps advancing under Policy + Guardrails |
| `completed` | Sequence finished (including LEARN/FEEDBACK as configured) |
| `paused` | Held; no new side effects |
| `failed` | Unrecoverable step error recorded |
| `aborted` | Kill switch or Guardrail abort |

---

## 3. Fixed step sequence

One cycle, fixed order — **no jumps**:

```text
COLLECT
  ↓
QUALIFY
  ↓
OPPORTUNITY
  ↓
SELECT
  ↓
EXPERIMENT
  ↓
DECIDE
  ↓
PRODUCE
  ↓
BUILD
  ↓
PUBLISH
  ↓
MEASURE
  ↓
LEARN
  ↓
FEEDBACK
  ↓
(end cycle → optional NEXT CYCLE by scheduler, not by jump)
```

### Forbidden transitions (examples)

| From | To | Allowed? |
|------|-----|----------|
| SELECT | BUILD | ❌ |
| OPPORTUNITY | PUBLISH | ❌ |
| EXPERIMENT (`running`) | DECIDE | ❌ |
| DECIDE (`no_decision` / `kill` without produce path) | PRODUCE | ❌ |
| PRODUCE without `execute` | BUILD | ❌ |

DECIDE may run only when the experiment is **completed** (Policy returns `no_decision` otherwise).

---

## 4. Step contracts (v0)

| Step | Uses existing backend | Orchestrator duty | Policy / Guardrail gate |
|------|----------------------|-------------------|-------------------------|
| COLLECT | discovery ingest / RSS | Run allowlisted sources only | Source whitelist |
| QUALIFY | Phase 2 quality | Persist qualification; drop ineligible from downstream sets | — |
| OPPORTUNITY | Phase 3 generate | Only from qualified set; cap by config | max opportunities prep |
| SELECT | deterministic rank | Apply eligibility + ranking from Policy | SELECT rules |
| EXPERIMENT | Phase 4 engine | At most `max_experiments_per_cycle` | readiness gates |
| DECIDE | Phase 5 record shape | Invoke **Policy evaluation**; write Decision with `decided_by=policy:…` | Core algorithm |
| PRODUCE | Phase 6 | Only if verdict `execute` and Guardrails pass | execute + snapshots |
| BUILD | Path A templates / static HTML microproduct | Only `allowed_templates` | template whitelist |
| PUBLISH | Phase 7 + channel adapter | Only `allowed_channels`; record publication | publish caps |
| MEASURE | analytics inputs | Collect configured metrics window | — |
| LEARN | Phase 8 learning | Emit LearningRecord; no silent lifecycle mutation | observational rules |
| FEEDBACK | Phase 9 shapes | Optional auto path only if Policy config enables; else skip | feedback limits |

**Reuse, don’t fork:** Orchestrator wires existing packages; it does not reimplement Phase logic.

---

## 5. SELECT (critical node)

Humans must not re-enter via vague choice.

1. Build **eligible** set per Policy eligibility.  
2. **Rank** deterministically per Policy ranking.  
3. Admit at most `max_opportunities_per_cycle` (v0 intent: **1**).  
4. Start at most `max_experiments_per_cycle` (v0 intent: **1**).

No LLM authority on SELECT.

---

## 6. Hard Guardrails (above Policy)

Guardrails are **not** suggestions. On violation → `aborted` or forced non-`execute` path; never “Policy said yes, so proceed.”

### System Kill Switch

```text
ORCHESTRATOR_ENABLED=false
```

When false:

- No **new** cycle may start  
- `abort_cycle(cycle_id)` must stop in-flight work at the next safe boundary (no new BUILD/PUBLISH)

Kill Switch is **outside** Policy authority.

### Non-overridable ceilings (v0)

| Guardrail | Effect |
|-----------|--------|
| Missing `criteria_snapshot` / `metrics_snapshot` on execute path | Block PRODUCE/BUILD/PUBLISH |
| Channel ∉ `allowed_channels` | Block PUBLISH |
| Template ∉ `allowed_templates` | Block BUILD |
| `max_spend_per_cycle` / `max_spend_per_week` exceeded | Block paid actions; prefer abort produce/publish |
| `max_publishes_per_cycle` / `max_publishes_per_week` exceeded | Block PUBLISH |
| Experiment not `completed` | Block DECIDE→execute path |
| Arbitrary code deploy | Block (not in whitelist) |

---

## 7. Whitelist v0 (operational)

Aligned with Policy configuration:

| Area | v0 allowlist |
|------|----------------|
| Build | `static_html_microproduct` only |
| Publish | `github_pages` only (target when publish automation lands; not enabled by this doc alone) |
| Sources | Only ingestion sources already supported and listed in config allowlist |

---

## 8. Failure and safety behavior

| Condition | Orchestrator behavior |
|-----------|------------------------|
| Policy → `no_decision` | Do not PRODUCE; mark step outcome; cycle may complete without publish |
| Policy → `kill` | Skip PRODUCE/BUILD/PUBLISH; continue MEASURE/LEARN if data exists |
| Policy → `iterate` | Schedule/record iteration under caps; no BUILD |
| Policy → `execute` but Guardrail fails | Treat as blocked; **no** publish; cycle `aborted` or failed produce path |
| Unhandled exception | `failed`; no partial publish without record |

**Safe default:** when uncertain, do **not** BUILD or PUBLISH.

---

## 9. Explicitly out of scope for P0

- No Orchestrator implementation code  
- No Scheduler / cron wiring  
- No new live market experiment  
- No real publish  
- No manual Opportunity pick as a substitute for SELECT design  
- No Path A behavior change  
- No removal of existing human gates  
- No claim of autonomy from documentation alone  

---

## 10. Control plane picture

```text
                ┌──────────────────────────┐
                │ Autonomous Policy v0     │
                │ + Hard Guardrails        │
                └────────────┬─────────────┘
                             ↓
Market → Signals → Opportunities → Experiments
                             ↓
                  Autonomous Decision
                             ↓
            Production → Build → Publish
                             ↓
                   Measure → Learn
                             ↓
                       Feedback
                             │
                             └────→ Market
```

Existing Phases 1–11 remain the **execution substrate**.  
P0 only locks the **control plane** contracts.

---

## 11. Document control

| Item | Value |
|------|--------|
| Contract phase | P0 |
| Implementation | **None** (design lock only) |
| Related | [`AUTONOMOUS_POLICY_V0.md`](AUTONOMOUS_POLICY_V0.md), [`OPERATING_RULES.md`](OPERATING_RULES.md) |
