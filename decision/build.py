"""Build Decision records (no automatic verdict from scores)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def generate_decision_id() -> str:
    return f"dec_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_decision(
    *,
    opportunity_id: str,
    verdict: str,
    reason: str,
    evidence_refs: list[str],
    decided_by: str,
    experiment_id: str | None = None,
    agent_suggestion: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    dec: dict[str, Any] = {
        "id": decision_id or generate_decision_id(),
        "opportunity_id": opportunity_id,
        "verdict": verdict,
        "reason": (reason or "").strip(),
        "evidence_refs": list(evidence_refs or []),
        "decided_by": decided_by,
        "decided_at": _now(),
    }
    if experiment_id:
        dec["experiment_id"] = experiment_id
    if agent_suggestion:
        dec["agent_suggestion"] = agent_suggestion
    return dec
