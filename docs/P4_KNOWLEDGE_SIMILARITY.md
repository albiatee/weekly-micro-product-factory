# P4 — Knowledge & Similarity Layer v0.1

**Status:** Implemented  
**Role:** Advisory information only — **never** a decision, block, or approval.

## Purpose

When a new idea arrives, search historical Factory knowledge:

- signals, opportunities, experiments, decisions, learning records, products

and return **similar** items with scores and matched terms.

> Similarity = information, not a decision.

## Architecture

```text
query text
    → normalize + tokenize
    → build corpus (read-only from data/* + products/weekly)
    → Jaccard/coverage score per document
    → ranked matches (deterministic)
```

| Module | Role |
|--------|------|
| `knowledge/normalize.py` | NFKC, lowercase, token filter, stopwords |
| `knowledge/index.py` | Materialize searchable docs from real stores |
| `knowledge/similarity.py` | Jaccard + query coverage blend ∈ [0,1] |
| `knowledge/search.py` | `search()` + `compare_idea()` |

## Scoring (v0.1)

```text
score = 0.55 * coverage(query, doc) + 0.45 * jaccard(query, doc)
(+0.1 if all query tokens ⊆ doc tokens and |query| ≥ 3, capped at 1.0)
```

- **Deterministic:** same query → same order (score desc, type asc, id asc)
- **Explainable:** `matched_terms` lists overlapping tokens
- **No LLM** in v0.1

## API

```http
GET /knowledge/search?q=...&limit=10&min_score=0.08&types=signal,opportunity,product
GET /knowledge/compare?q=...&limit=5
```

Both responses include `"advisory": true, "decision": null`.

## Comparison fields

| Field | Rule |
|-------|------|
| `common_concepts` | Matched tokens |
| `differences` | Query tokens not in match |
| `previous_solution` | From entity if present (e.g. solution_type, product title) |
| `previous_outcome` | Real verdict/status **or** `"not available"` — never invented success |
| `learning_evidence` | Only if learning record exists |

## Dashboard

Panel **Knowledge** in `dashboard/index.html`: textarea + call to local API `127.0.0.1:8000`.

## Limitations

- Lexical only (no embeddings, synonyms, or Arabic morphology depth)
- English/Arabic stopwords are minimal
- No cross-language semantic matching
- Does not prevent duplicates
- Does not run orchestrator or change stores

## Future upgrade path

- Optional embedding index (still advisory)
- Link experiment outcomes into comparison when Phase 5 data exists
- Dashboard offline fallback using a prebuilt knowledge snapshot JSON

## Safety

Read-only · no decision · no build · no publish · no orchestrator trigger from this layer.
