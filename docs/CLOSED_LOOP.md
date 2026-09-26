# Closed Loop — Discovery Feedback (Phase 9)

## Purpose

Feed Analytics/Learning observations back into Discovery **as human-gated hints**, not automatic Opportunities.

```text
Analytics / Learning
        ↓
Discovery Feedback (proposed)
        ↓
Human Review
     ↙       ↘
 reject     approve
              ↓
        convert-to-signal (explicit)
              ↓
            Signal
              ↓
        Signal Quality (Phase 2)
              ↓
      qualified / review / rejected
              ↓
          Opportunity (only if qualified)
```

## Feedback lifecycle

`proposed` → `approved` | `rejected` | `deferred`  
`approved` → `converted` (after explicit Signal conversion)  
Legacy `accepted` = approved + converted in one convenience command.

## Human review

`approve` / `reject` / `defer` require `reviewed_by` (+ optional notes).  
No confidence score may skip review.

## Conversion

Only **approved** feedback → Signal via existing Phase 2 ingest.  
Creating a Signal does **not** create an Opportunity.

## Provenance

Signal.meta includes `discovery_hint_id`, `source_learning_id`, `source_opportunity_id`.

## Idempotency

- One active hint per (learning_id + normalized text)
- Re-convert of already converted returns existing signal

## Not Phase 9

No automatic approve, no auto Opportunity, no pilot, no hardening redesign.
