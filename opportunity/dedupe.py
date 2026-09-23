"""Basic Opportunity deduplication (deterministic, non-semantic)."""
from __future__ import annotations

import re
from typing import Any


def _norm(text: str) -> str:
    t = (text or "").strip().lower()
    return re.sub(r"\s+", " ", t)


def fingerprint(opp: dict[str, Any]) -> str:
    """Prefer identical signal set; else normalized problem text."""
    sids = tuple(sorted(str(x) for x in (opp.get("signal_ids") or [])))
    if sids:
        return "signals:" + ",".join(sids)
    return "problem:" + _norm(str(opp.get("problem") or ""))


def find_duplicate(
    candidate: dict[str, Any], existing: dict[str, dict[str, Any]]
) -> str | None:
    fp = fingerprint(candidate)
    if fp in ("signals:", "problem:"):
        return None
    for oid, opp in existing.items():
        if fingerprint(opp) == fp:
            return oid
    return None
