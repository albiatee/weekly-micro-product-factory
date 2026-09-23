# Phase 9 — Discovery Feedback Loop

## Purpose

Close the loop from **Learning** back to **Discovery** with a **human review gate**.

```
Market → Signals → Opportunities → Experiments → Decisions
→ Production → Distribution → Analytics → Learning
→ Discovery Hints → Human Review → Signals → …
```

**Rule:** `Learning → Hint → Human Review → Signal`  
**Not:** `Learning → Automatic Signal → Automatic Opportunity`

## Discovery Hint (`dh_...`)

Required: id, opportunity_id, hint, status, source_learning_id, created_at, updated_at  

Optional: source_experiment_id, source_decision_id, rationale, created_by, resulting_signal_id  

Statuses: `proposed` → `accepted` | `rejected` | `deferred` (terminal)

## Learning → Hint

Only from existing LearningRecord with non-empty `next_signals_hint`.  
No invented demand/revenue claims.

## Human Review

- `accept` → creates Signal (Phase 2 path) then marks hint accepted  
- `reject` / `defer` → terminal, no Signal  

## Hint → Signal

- `source=manual` + `meta.source_detail=discovery_feedback`  
- meta: discovery_hint_id, source_learning_id, opportunity_id  
- Uses Phase 2 normalize/validate/dedupe/store  
- **Does not** create Opportunity (Phase 3 remains manual)

## Deduplication

Active duplicate = same `source_learning_id` + normalized hint text while status is `proposed` or `accepted`.

## Atomicity

On accept: validate → build/validate Signal → **write Signal first** → then mark hint `accepted`.  
If hint update fails after Signal write, error is explicit (possible orphan Signal).

## CLI

```bash
python scripts/manage_discovery_feedback.py create --learning-id lr_xxx
python scripts/manage_discovery_feedback.py accept --hint-id dh_xxx
python scripts/manage_discovery_feedback.py reject --hint-id dh_xxx
python scripts/manage_discovery_feedback.py defer --hint-id dh_xxx
python scripts/manage_discovery_feedback.py list
# + --dry-run
```

## Does NOT do

- Auto Opportunity / Decision / Experiment / Production / Distribution  
- Score mutation  
- External APIs / LLM discovery  
- Phase 10 autonomous discovery  

## Storage

`data/discovery_hints/index.json`  
Signals only via existing `data/signals/` after accept.
