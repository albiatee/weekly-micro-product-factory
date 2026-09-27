"""Learning record shapes — conservative classification."""
from __future__ import annotations

from typing import Any, Literal

ObservationKind = Literal["observed", "derived", "inferred", "unknown"]


def observation(
    *,
    kind: ObservationKind,
    statement: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "statement": statement,
        "evidence": evidence or {},
    }
