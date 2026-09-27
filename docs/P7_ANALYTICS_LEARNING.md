# P7 — Real Analytics + Learning v0.1

## Flow

```text
Build (P6) / product id
  → user/system supplies metrics (scripts/record_analytics.py)
  → Analytics record (data/analytics/index.json → records)
  → Learning record (deterministic observations + lessons)
  → Knowledge search surfaces learning (advisory only)
```

## Analytics schema

```json
{
  "id": "anl_...",
  "build_id": "bld_...|null",
  "opportunity_id": "opp_...|null",
  "product_id": "string|null",
  "period": "string",
  "metrics": {
    "raw": { "visits": 100, "signups": 10 },
    "derived": { "signup_rate": 0.1, "conversion_rate": null }
  },
  "source": "user_supplied",
  "source_note": "Metrics are user/system supplied — not invented market evidence.",
  "captured_at": "ISO-8601",
  "status": "recorded|not_available",
  "notes": null
}
```

Raw keys: `visits`, `signups`, `conversions`, `revenue`, `refunds`, `active_users`.

Derived: `signup_rate`, `conversion_rate`, `refund_rate` — **null** if inputs missing or denominator ≤ 0.

## Learning schema

```json
{
  "id": "lr_...",
  "source_analytics_id": "anl_...",
  "build_id": null,
  "opportunity_id": null,
  "product_id": null,
  "observations": [
    { "kind": "observed|derived|inferred|unknown", "statement": "...", "evidence": {} }
  ],
  "lessons": ["descriptive only — no causal design claims"],
  "confidence": "none|low|medium",
  "created_at": "...",
  "advisory": true
}
```

v0.1 does **not** emit `inferred` causal lessons.

## CLI

```bash
python scripts/record_analytics.py --build-id bld_x --metrics-json '{"visits":100,"signups":10}' --generate-learning
python scripts/record_analytics.py --product-id weekly/2026-w52 --not-available
```

## API

- `GET /analytics` · `GET /analytics/{id}`
- `GET /learning` · `GET /learning/{id}`
- `POST /analytics/record` (local; `live_publish: false`)

## Limitations

- No public traffic measurement (no publish in P7)
- Metrics must be supplied — never scraped as fake market proof
- Similarity remains non-blocking

## Path A

Does not modify `products/weekly`, `weekly-build.yml`, or Path A agents/templates.
