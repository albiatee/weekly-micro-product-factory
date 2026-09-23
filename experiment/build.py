"""Build Experiment dicts from Opportunities (no fabricated results)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def generate_experiment_id() -> str:
    return f"exp_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_experiment(
    opportunity: dict[str, Any],
    *,
    experiment_type: str,
    hypothesis_test: str | None = None,
    measurement_plan: str | dict[str, Any] | None = None,
    success_threshold: dict[str, Any] | None = None,
    channel: str | None = None,
    created_by: str = "system:experiment_engine",
    experiment_id: str | None = None,
) -> dict[str, Any]:
    """Create a planned Experiment linked to an existing Opportunity."""
    oid = opportunity.get("id")
    if not oid:
        raise ValueError("opportunity must have id")

    hyp = hypothesis_test
    if not hyp:
        # Derive a testable statement from opportunity hypothesis field if present
        base = opportunity.get("hypothesis") or opportunity.get("problem") or opportunity.get("title")
        hyp = f"Test whether interest appears for: {base}"

    now = _now()
    exp: dict[str, Any] = {
        "id": experiment_id or generate_experiment_id(),
        "opportunity_id": str(oid),
        "status": "planned",
        "experiment_type": experiment_type,
        "hypothesis_test": str(hyp).strip(),
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    if measurement_plan is not None:
        exp["measurement_plan"] = measurement_plan
    if success_threshold is not None:
        exp["success_threshold"] = success_threshold
    if channel:
        exp["channel"] = channel
    return exp
