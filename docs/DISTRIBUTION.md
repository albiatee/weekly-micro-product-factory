# Distribution Layer (Phase 7)

## Purpose

Create an **auditable distribution plan** from a **ready Production Specification**.

Creating a Distribution record does **NOT** mean the product was published externally.

## Entry gate

- Production Spec exists and status ∈ {ready, in_progress, completed}
- Linked Decision `verdict == execute`
- Decision ↔ Opportunity ↔ Experiment consistent
- Experiment completed
- Opportunity status `building` or `shipped`

**Do not** create Distribution directly from Opportunity/Decision without a Production Spec.

## Lifecycle

```text
planned → prepared → published | failed
                   ↘ cancelled
```

Legacy statuses (`ready`, `running`, `completed`) remain valid for the older opportunity+artifact path.

## Channels

`own_site`, `landing_page`, `product_catalog`, `community_post`, `social_post`, `email`,  
plus legacy: `github`, `telegram`, `reddit`, `x`, `direct`, `seo`, `community`, `other`.

**No network calls. No API integrations.** External channels are records only until an operator calls `record-publication`.

## Traceability

```text
Distribution.production_spec_id
  → ProductionSpec.decision_id / experiment_id / opportunity_id
  → source_signal_ids
```

## Idempotency

One **active** plan per (`production_spec_id`, `channel`).

## Publication semantics

| Status | Meaning |
|--------|---------|
| planned | Intent recorded |
| prepared | Message/artifact prepared locally |
| published | Operator **explicitly** recorded success |
| failed | Operator recorded failure |

## CLI

```bash
python scripts/manage_distribution.py create-from-spec --production-spec-id prd_... --channel landing_page
python scripts/manage_distribution.py prepare --plan-id dist_...
python scripts/manage_distribution.py record-publication --plan-id dist_... --success true
python scripts/manage_distribution.py list
```

Legacy: `create` from shipped opportunity + `production_ref` still available.

## Not in Phase 7

Analytics, learning, discovery feedback, real social/email sending, ads, schedulers.
