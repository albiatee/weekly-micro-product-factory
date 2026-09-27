# P2 — Dashboard / Control Hub v0.1

## Scope

Read-only control hub over **real** Factory data:

- Overview counts
- Signals / Opportunities / Experiments / Products / Cycles
- Ideas → link to GitHub Issues (Path A)
- Cycles → CLI dry-run instructions (no server-side run on Pages)

## Files

| Path | Role |
|------|------|
| `dashboard/index.html` | UI |
| `dashboard/data.json` | Snapshot built from stores |
| `scripts/build_dashboard_data.py` | Rebuild snapshot |

## Rebuild

```bash
python scripts/build_dashboard_data.py
```

## Not in v0.1

- Backend API (P3)
- Running orchestrator from the browser
- Live experiment runner (P5)
- Auto publish (P7)

## Roadmap pointer

P2 → P3 API → P4 Similarity → P5 Experiments → P6 Build → P7 Publish → P8 n8n → P9 Analytics → P10 Shopify → P11 Closed autonomous loop
