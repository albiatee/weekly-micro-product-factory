"""Search and compare — advisory information only."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from knowledge.index import build_corpus
from knowledge.normalize import token_set
from knowledge.similarity import score_pair

ROOT = Path(__file__).resolve().parents[1]

ENTITY_TYPES = frozenset(
    {"signal", "opportunity", "experiment", "decision", "learning", "product"}
)


def search(
    query: str,
    *,
    entity_types: list[str] | None = None,
    limit: int = 10,
    min_score: float = 0.08,
    root: Path | None = None,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "query": query,
            "matches": [],
            "count": 0,
            "note": "empty query — no search performed",
            "advisory": True,
            "decision": None,
        }

    types = set(entity_types) if entity_types else set(ENTITY_TYPES)
    types &= ENTITY_TYPES
    corpus = build_corpus(root or ROOT)
    qtokens = token_set(q)

    scored: list[dict[str, Any]] = []
    for doc in corpus:
        if doc["entity_type"] not in types:
            continue
        doc_tokens = frozenset(doc.get("tokens") or [])
        score, matched = score_pair(qtokens, doc_tokens)
        if score < min_score:
            continue
        scored.append(
            {
                "entity_type": doc["entity_type"],
                "entity_id": doc["entity_id"],
                "similarity_score": score,
                "matched_terms": matched,
                "source": doc.get("source"),
                "summary": doc.get("summary") or None,
                "extra": doc.get("extra") or {},
            }
        )

    # Deterministic order: score desc, type asc, id asc
    scored.sort(
        key=lambda m: (-m["similarity_score"], m["entity_type"], m["entity_id"])
    )
    matches = scored[: max(0, int(limit))]

    return {
        "query": q,
        "matches": matches,
        "count": len(matches),
        "corpus_size": len(corpus),
        "advisory": True,
        "decision": None,
        "note": "Similarity is informational only — does not approve, reject, or rank for production.",
    }


def compare_idea(
    idea_text: str,
    *,
    limit: int = 5,
    root: Path | None = None,
) -> dict[str, Any]:
    """new idea vs historical matches — no fabricated outcomes."""
    result = search(idea_text, limit=limit, root=root)
    comparisons: list[dict[str, Any]] = []
    qtokens = token_set(idea_text)

    for m in result["matches"]:
        # Re-load doc tokens via matched_terms only (already computed)
        common = list(m.get("matched_terms") or [])
        # Differences: query tokens not in match (best-effort from matched set)
        query_only = sorted(qtokens - set(common))[:12]

        prev_solution = None
        prev_outcome = None
        learning = None
        extra = m.get("extra") or {}

        if m["entity_type"] == "product":
            prev_solution = m.get("summary")
            prev_outcome = "not available"  # no experiment linkage invented
        elif m["entity_type"] == "opportunity":
            prev_solution = extra.get("solution_type") or None
            prev_outcome = "not available"
        elif m["entity_type"] == "experiment":
            prev_solution = None
            prev_outcome = (
                extra.get("status")
                if extra.get("has_results")
                else "not available"
            )
        elif m["entity_type"] == "decision":
            prev_outcome = extra.get("verdict") or "not available"
        elif m["entity_type"] == "learning":
            learning = m.get("summary")
            prev_outcome = extra.get("outcome") if extra.get("outcome") is not None else "not available"
        else:
            prev_outcome = "not available"

        comparisons.append(
            {
                "new_idea": idea_text[:500],
                "historical_match": {
                    "entity_type": m["entity_type"],
                    "entity_id": m["entity_id"],
                    "summary": m.get("summary"),
                    "source": m.get("source"),
                    "similarity_score": m["similarity_score"],
                },
                "common_concepts": common,
                "differences": {
                    "query_terms_not_in_match": query_only,
                },
                "previous_solution": prev_solution,
                "previous_outcome": prev_outcome,
                "learning_evidence": learning,
            }
        )

    return {
        "idea": idea_text,
        "comparisons": comparisons,
        "count": len(comparisons),
        "advisory": True,
        "decision": None,
        "note": "Comparison is informational. Absence of experiment/learning data yields 'not available', never inferred success.",
    }
