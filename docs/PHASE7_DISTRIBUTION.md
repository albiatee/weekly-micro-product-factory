# Phase 7 — Distribution Layer

## Purpose

Record and manage **manual distribution** of **shipped** products.

```
Opportunity(shipped) + production_ref + real artifact
        ↓
Distribution Plan (dist_...)
        ↓
Actions (dact_...) / Results (operator-supplied)
        ↓
completed | cancelled | paused
```

Distribution is **not** market validation and **not** Analytics/Learning.

## Requirements to create a plan

- Opportunity `status == shipped`
- `production_ref` present
- Artifact resolvable (`index.html` under path) when check enabled
- Valid `channel`

Rejected statuses: hypothesized, experimenting, building, killed, iterating, etc.

## Contracts

### Plan (`dist_...`)

id, opportunity_id, production_ref, status, channel, objective, audience, created_by, created_at, updated_at, results?

Statuses: `planned` → `ready` / `running` / `cancelled` → … → `completed` | `cancelled` (terminal)

Channels: github, telegram, reddit, x, direct, seo, community, other

### Action (`dact_...`)

id, distribution_id, channel, action_type, status, created_at, executed_at?, result?, notes?

action_type: publish, announce, submit, share, manual_post, other

## Idempotency

- One **active** plan per (opportunity_id, channel) (not completed/cancelled)
- Duplicate executed action with same plan + action_type + notes refused

## What Phase 7 does NOT do

- Rebuild products / change production_ref / run Production Bridge
- Modify weekly-build, issue-intake, catalog, products/weekly
- External API marketing automation
- Fabricate metrics or revenue
- Analytics Engine / Learning Engine

## CLI

```bash
python scripts/manage_distribution.py create \
  --opportunity-id opp_xxx --channel telegram --objective "Announce shipped tool"

python scripts/manage_distribution.py start --plan-id dist_xxx
python scripts/manage_distribution.py record-action --plan-id dist_xxx --action-type manual_post --notes "Posted"
python scripts/manage_distribution.py record-result --plan-id dist_xxx --metrics-json '{"clicks":10}'
python scripts/manage_distribution.py complete --plan-id dist_xxx
python scripts/manage_distribution.py list
```

`--dry-run` available on mutating commands.

## Storage

`data/distribution/index.json` — `{ plans, actions }`

## Future

Phase 8+ may consume results for Analytics/Learning without changing this contract.
