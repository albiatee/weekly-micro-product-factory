# Phase 6 — Production Bridge

## Purpose

Connect **Decision(verdict=execute)** + **Opportunity(status=building)** to the **existing template-based product artifacts**, without rewriting `weekly-build.yml`.

```
Decision execute → Opportunity building
        ↓
Production Bridge (this phase)
        ↓
products/bridge/<opportunity_id>/
        ↓
Opportunity status = shipped + production_ref
```

## Why a Bridge

- Keep GitHub Issue → vote → `weekly-build` path **unchanged**
- Add Opportunity-driven path that reuses **templates/** only
- Do **not** make Opportunities mandatory for weekly production

## Gate requirements

All required:

1. Opportunity exists and `status == building`
2. `latest_decision_id` points to a real Decision
3. That Decision: `verdict == execute` and same `opportunity_id`
4. No existing `production_ref` (idempotency)
5. `solution_type` supported

## Supported solution types

**Phase 6 supports only:** `digital_micro`

Unsupported for now (clear rejection):  
`content_pack`, `concierge`, `saas`, `physical_hybrid`, `marketplace`, `unknown`

## Opportunity → artifact mapping

| Opportunity field | Use |
|-------------------|-----|
| title / problem | meta.json title/description |
| solution_type | must be digital_micro |
| latest_decision_id | stored on meta + production_ref |
| templates/calculator (or first available) | HTML body |

**Does not** write `catalog/index.json` (weekly-build owns that path).

## production_ref

```json
{
  "path": "products/bridge/opp_...",
  "template": "calculator",
  "decision_id": "dec_...",
  "opportunity_id": "opp_...",
  "kind": "digital_micro_bridge",
  "built_at": "ISO-8601"
}
```

## Idempotency

If `production_ref` is set → **refuse** second build.  
If target directory exists → **refuse**.

## Failure handling

On failure: Opportunity stays **`building`** (or unchanged); no fake `production_ref`; no `shipped`.

## shipped condition

Only when:

1. `index.html` artifact exists under `products/bridge/...`
2. `meta.json` written
3. Opportunity transition `building → shipped` validates
4. `production_ref` set

## CLI

```bash
python scripts/production_bridge.py build --opportunity-id opp_xxx
python scripts/production_bridge.py build --opportunity-id opp_xxx --dry-run
```

## What Phase 6 does NOT do

- Rewrite weekly-build / issue-intake  
- Distribution (Telegram, social, ads) — Phase 7  
- Analytics / Learning  
- Auto-build from score / passed / threshold alone  

## Phase 7 boundary

Stops at **shipped**. Distribution starts later.
