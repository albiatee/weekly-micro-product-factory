"""Deterministic token-set similarity (Jaccard + coverage)."""
from __future__ import annotations

from typing import Any

from knowledge.normalize import token_set


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / len(union)


def coverage(query: frozenset[str], doc: frozenset[str]) -> float:
    """Fraction of query tokens found in doc."""
    if not query:
        return 0.0
    return len(query & doc) / len(query)


def score_pair(query_tokens: frozenset[str], doc_tokens: frozenset[str]) -> tuple[float, list[str]]:
    """Combined score in [0, 1]. Explainable matched terms."""
    if not query_tokens:
        return 0.0, []
    inter = sorted(query_tokens & doc_tokens)
    j = jaccard(query_tokens, doc_tokens)
    c = coverage(query_tokens, doc_tokens)
    # Prefer coverage for short queries; blend with Jaccard
    score = 0.55 * c + 0.45 * j
    # exact token identity boost when all query tokens present
    if query_tokens <= doc_tokens and len(query_tokens) >= 3:
        score = min(1.0, score + 0.1)
    return round(min(1.0, max(0.0, score)), 4), inter


def score_text(query: str, doc_text: str) -> tuple[float, list[str]]:
    return score_pair(token_set(query), token_set(doc_text))
