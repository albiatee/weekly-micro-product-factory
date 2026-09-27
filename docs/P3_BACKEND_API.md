# P3 — Backend API v0.1

**Status:** Implemented (local-only)  
**Stack:** FastAPI + uvicorn  
**Bind default:** `127.0.0.1:8000`

## Architecture

```text
Dashboard / curl
       ↓
   Factory API  (api/app.py)     ← interface only
       ↓
  store_readers (read JSON)  |  orchestrator.run_cycle(dry_run=True)
       ↓
  data/* + products/weekly       ← source of truth (unchanged writers)
```

| Layer | Role |
|-------|------|
| API | HTTP interface |
| Orchestrator | Sequencing (dry-run via API) |
| Policy / Guardrails | Unchanged; not bypassed |
| Factory data | Source of truth |

## Endpoints

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/health` | Liveness; `live_execution: false` |
| GET | `/signals` | Read signals store |
| GET | `/opportunities` | Read opportunities |
| GET | `/experiments` | Read experiments |
| GET | `/decisions` | Read decisions |
| GET | `/production-specs` | Read production specs |
| GET | `/distributions` | Read distribution plans |
| GET | `/learning` | Read learning records |
| GET | `/cycles` | Read orchestrator cycles |
| GET | `/products` | Scan `products/weekly/*/meta.json` |
| POST | `/cycles/dry-run` | Orchestrator **dry-run only** |
| POST | `/cycles/live` | **403 Forbidden** |
| * | `/publish`, `/build` | **403 Forbidden** |

### Response shape (collections)

```json
{
  "items": { "id": { "...": "..." } },
  "count": 0,
  "updated_at": null,
  "store_status": "ok|missing|error"
}
```

Malformed JSON stores return empty `items` with `store_status: error` (no 500).

## Security boundary

- Default bind **127.0.0.1 only** (`scripts/run_api.py` refuses non-local host)
- No complex auth in v0.1 (local process trust)
- No internet exposure by design
- No endpoint to bypass Policy/Guardrails
- API does not implement arbitrary writes to `data/*` (dry-run may persist a cycle record only if `persist=true`)
- Live execution explicitly forbidden

## Local usage

```bash
pip install -r requirements.txt
python scripts/run_api.py --host 127.0.0.1 --port 8000
```

```bash
curl -s http://127.0.0.1:8000/health | jq
curl -s http://127.0.0.1:8000/opportunities | jq '.count'
curl -s -X POST http://127.0.0.1:8000/cycles/dry-run \
  -H 'Content-Type: application/json' \
  -d '{"stop_after":"SELECT","persist":false}' | jq '.dry_run,.ok'
```

## Out of scope (P3)

- Live publishing / build
- Real experiment auto-start
- Shopify, n8n
- Autonomous live loop
- Similarity engine (P4)
- Mobile app
- Public deployment / TLS / multi-user auth

## Tests

`tests/test_api_p3.py`
