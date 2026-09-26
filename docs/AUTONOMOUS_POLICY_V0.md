# Autonomous Decision Policy v0

**Status:** P0 contract — locked for design; **not** implemented in code.  
**policy_id:** `policy_autonomous_factory_v0`  
**version:** `0.1.0`  
**mode:** `autonomous`

> This document defines **authorization** for lifecycle transitions under autonomous mode.  
> It does **not** enable autonomous mode by itself. Human gates in Phases 1–11 remain in force until autonomous mode is explicitly activated in a later phase.

---

## 1. Separation of concerns

| Layer | Responsibility |
|-------|----------------|
| **Orchestrator** | *What* to run and *when* (sequence, scheduling, cycle lifecycle) |
| **Policy** (this doc) | *Whether* the next step is **allowed** under rules |
| **Guardrails** | Hard ceilings that **cannot** be overridden even if Policy says yes |
| **LLM / Agents** | Extract or summarize evidence only — **never** authorize |

```text
System Kill Switch
       ↓
Hard Guardrails
       ↓
Policy evaluation   ← authorization
       ↓
Orchestrator step
       ↓
LLM / Agents        ← suggestion only, not authorization
```

**Invariant:** `LLM suggestion ≠ authorization`.  
**Invariant:** `Policy evaluation = authorization` (subject to Guardrails).  
**Invariant:** No “smart override” that lets a model bypass deterministic rules.

---

## 2. Decision outputs (only)

| Verdict | Meaning |
|---------|---------|
| `execute` | Authorize Production Spec path (then Build/Publish only if Guardrails allow) |
| `iterate` | Do not produce; allow another experiment under iteration limits |
| `kill` | Stop this opportunity branch for the cycle |
| `no_decision` | Preconditions missing; Orchestrator must not advance to PRODUCE |

No other verdict strings are valid for autonomous policy evaluation.

---

## 3. Core decision algorithm (deterministic)

Evaluate **in order**. First matching terminal rule wins.

```text
IF experiment.status != completed
    → no_decision

IF measurement_invalid
    → kill

IF failure_criteria_met
    → kill

IF success_criteria_met
   AND risk <= max_risk
   AND estimated_cost <= remaining_budget
   AND publish_channel ∈ allowed_channels
   AND build_template ∈ allowed_templates
   AND cycle_limits_not_exceeded
    → execute

IF iteration_count < max_iterations
    → iterate

ELSE
    → kill
```

### Definitions (v0)

| Term | Definition |
|------|------------|
| `measurement_invalid` | Results missing, schema-invalid, or not aligned with the pre-registered `measurement_plan` |
| `failure_criteria_met` | Pre-registered failure criteria evaluate true against `metrics_snapshot` |
| `success_criteria_met` | Pre-registered success criteria evaluate true against `metrics_snapshot` |
| `risk` | Numeric score in `[0, 1]` from a **fixed** checklist (v0: missing snapshots, channel not whitelisted, template not whitelisted, budget unknown → treat as high risk) |
| `max_risk` | From Policy configuration (not invented at runtime) |
| `estimated_cost` / `remaining_budget` | From cycle budget accounting; if unknown → **cannot** `execute` |
| `cycle_limits_not_exceeded` | All `max_*` counters for this cycle/week still under config |

**Grey zone:** If neither success nor failure criteria are clearly met, do **not** `execute`. Use `iterate` only if under `max_iterations`; else `kill`.

---

## 4. Decision Record (extends existing Decision entity)

Autonomous decisions **reuse** the existing Decision contract. Additional required fields when `decided_by` is policy-scoped:

| Field | Required | Example |
|-------|----------|---------|
| `decided_by` | yes | `policy:policy_autonomous_factory_v0` |
| `policy_version` | yes | `0.1.0` |
| `cycle_id` | yes | `cyc_<id>` |
| `verdict` | yes | `execute` \| `iterate` \| `kill` \| (record `no_decision` only as cycle log, not as execute path) |
| `rule_hits` | yes | ordered list of rule ids that matched |
| `evidence_refs` | yes | existing refs (`exp_…`, `sig_…`, …) |
| `criteria_snapshot` | yes for any terminal verdict affecting produce | frozen criteria at decision time |
| `metrics_snapshot` | yes for any terminal verdict affecting produce | frozen metrics at decision time |
| `reason` | yes | human-readable, derived from rule_hits |

**Hard rule:** `execute` is **forbidden** if `criteria_snapshot` or `metrics_snapshot` is missing or empty.

`no_decision` does not create a Production Spec and does not count as a successful cycle decision for publish limits.

---

## 5. SELECT rules (no human back-door)

Policy constrains selection; Orchestrator applies it.

### Configuration keys (values live in Policy config, not hard-coded in engine logic)

| Key | Purpose |
|-----|---------|
| `max_opportunities_per_cycle` | Cap opportunities admitted per cycle |
| `max_experiments_per_cycle` | Cap experiments started per cycle |
| `max_iterations_per_opportunity` | Cap iterate loops |
| `minimum_qualified_source_count` | Minimum qualified signals linked (v0 default intent: ≥ 1) |

### Eligibility (all must hold)

```text
eligible =
    evidence_ready
    AND qualified_source_count >= minimum_qualified_source_count
    AND no_active_experiment_on_opportunity
    AND within_cycle_limits
```

### Ranking (deterministic)

1. Compute `score` from **named fields only** (v0 suggested tuple, lexicographic / weighted as fixed in config):
   - `evidence_ready` (bool)
   - aggregate evidence strength rank
   - number of linked `signal_ids`
   - recency of latest source signal (`captured_at`)
2. Sort descending by score; ties broken by `opportunity_id` ascending (stable).
3. Take top `max_opportunities_per_cycle` from the **eligible** set only.

**Forbidden:** “pick what looks best”, LLM ranking as authority, or silent inclusion of non-eligible rows.

---

## 6. Whitelist v0 (Policy configuration surface)

### Sources
Only sources the current ingestion path understands and that appear on an allowlist in config (initial set = feeds/manual paths already proven in-repo). No arbitrary web scrape authorization in v0.

### Build

```text
allowed_templates:
  - static_html_microproduct
```

No arbitrary code generation or unrestricted deployment in v0.

### Publish (target for later P3; Policy must still check)

```text
allowed_channels:
  - github_pages
```

### Limit keys (values set in config, not in prose alone)

```text
max_spend_per_cycle
max_spend_per_week
max_opportunities_per_cycle
max_experiments_per_cycle
max_iterations_per_opportunity
max_publishes_per_cycle
max_publishes_per_week
max_risk
```

---

## 7. What Policy does **not** do

- Does not schedule cycles (Orchestrator)
- Does not override Kill Switch or Guardrails
- Does not invent market size, willingness to pay, or success metrics after the fact
- Does not modify Path A workflows
- Does not delete human gates from legacy mode
- Does not claim the system is autonomous merely by setting `decided_by=policy:…`

---

## 8. Activation

Autonomous evaluation applies **only** when:

1. Control-plane docs (P0) accepted, and  
2. A later phase explicitly enables autonomous mode for a cycle (`mode=autonomous` + `ORCHESTRATOR_ENABLED=true`), and  
3. Guardrails and whitelist config are present.

Until then, existing human Decision / Feedback / publication gates remain authoritative.

---

## 9. Document control

| Item | Value |
|------|--------|
| Contract phase | P0 |
| Implementation | **None** (design lock only) |
| Related | [`ORCHESTRATOR_CONTRACT_V0.md`](ORCHESTRATOR_CONTRACT_V0.md), [`OPERATING_RULES.md`](OPERATING_RULES.md) |
