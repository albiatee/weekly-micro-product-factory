# Opportunity Evidence (Phase 3)

## Purpose

Phase 2 decides whether a **Signal** may enter opportunity generation.  
Phase 3 ensures each **Opportunity** states:

- what is **evidenced** (traceable to Signals)
- what is **assumed** (untested)
- what is still **unknown**

This is **not** market validation and **does not** run experiments.

## Evidence model

Each Opportunity carries:

| Field | Role |
|-------|------|
| `evidence[]` | Items with `type`, `signal_id`, `summary`, `strength`, optional `url`/`source` |
| `assumptions[]` | Untested claims (`assumption`, `importance`, `confidence`, `status`) |
| `unknowns[]` | Explicit gaps (no invented values) |
| `evidence_strength` | Deterministic roll-up at **opportunity** level |
| `problem` / `problem_statement` | Problem text |
| `audience` / `target_user` | Who is affected |
| `signal_ids` | Traceability anchors |
| `solution_type` / `solution_direction` | Hypothesis only |

Evidence items must reference `sig_…` ids. No free-floating “facts”.

## Evidence vs assumptions

| Evidence | Assumption |
|----------|------------|
| Excerpt/problem from a linked Signal | “Users will pay” |
| Classification strength on that Signal | “Problem is frequent enough” |
| Multi-signal theme (weak by design) | Anything not in source text |

**Assumptions are never stored inside `evidence[]`.**

## Unknowns

Default unknowns include willingness to pay, market size, frequency, geography when not on signals.  
Do not fill unknowns with guesses.

## Traceability

```text
Opportunity.signal_ids[]
    → Signal.id
        → Signal.url / source / raw_text
Opportunity.evidence[].signal_id
    → same Signal set
```

Orphan opportunities without `signal_ids` are not evidence-ready (except possible legacy draft — not used for experimenting).

## Evidence readiness (`is_evidence_ready`)

Required for moving an Opportunity toward **experimenting** (enforced in `start_experiment`):

1. Problem statement (≥ ~20 chars)
2. Target user / audience
3. Non-empty `signal_ids`
4. Non-empty `evidence` with signal references + summaries
5. `assumptions` list present
6. `unknowns` list present

**Strong Signal evidence_strength does not make Opportunity validated.**  
Roll-up caps a single strong signal at **medium** opportunity strength.

## Lifecycle implications

| Status | Evidence |
|--------|----------|
| `hypothesized` | Should include evidence layer when generated via engine |
| → `experimenting` | **Blocked** if not `is_evidence_ready` |
| Experiments themselves | Phase 4+ |

## Examples

**Ready (synthetic):** problem from qualified signal + evidence item pointing at `sig_…` + default assumptions/unknowns.

**Not ready:** empty evidence, missing signal_ids, problem one word, evidence summary without `signal_id`.

## Limitations

- Heuristic audience extraction remains weak (“unspecified…” is allowed but honesty is preferred).
- Does not measure real-world demand.
- Does not implement experiment types or decision criteria.
