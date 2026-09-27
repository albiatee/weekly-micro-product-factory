# P6 — Automated Build v0.1

## Flow

```text
Decision (verdict=execute)
  → Production Spec
  → Bridge copy template → products/bridge/<opp>/
  → Validate index.html + meta.json
  → Build log data/builds/
```

## Hard rules

| Rule | Enforcement |
|------|-------------|
| Only `execute` | Reject other verdicts |
| Opportunity `building` | Required |
| Kind | `static_html_microproduct` → `digital_micro` templates |
| No public publish | No distribution calls |
| No Path A | Does not write `products/weekly` or `weekly-build.yml` |
| Fail-safe | Bridge failure → status failed, no shipped claim |
| Traceability | `bld_*` log with steps |

## CLI

```bash
python scripts/run_build.py --decision-id dec_... --dry-run
python scripts/run_build.py --decision-id dec_...
```

## API

`POST /builds/run` with `{ "decision_id", "dry_run" }` — always `live_publish: false`.

## Out of scope

Shopify · n8n · GitHub Pages publish · arbitrary code generation
