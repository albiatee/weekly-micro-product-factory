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
    success_criteria: str | dict[str, Any] | None = None,
    failure_criteria: str | dict[str, Any] | None = None,
    target_population: str | None = None,
    assumptions_tested: list[str] | None = None,
    duration: str | None = None,
    observation_window: str | None = None,
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
        base = opportunity.get("hypothesis") or opportunity.get("problem") or opportunity.get("title")
        hyp = f"Test whether the hypothesized solution addresses: {base}"

    pop = target_population
    if not pop:
        pop = str(opportunity.get("audience") or opportunity.get("target_user") or "").strip()
        if not pop:
            pop = "unspecified population (set target_population before start)"

    now = _now()
    exp: dict[str, Any] = {
        "id": experiment_id or generate_experiment_id(),
        "opportunity_id": str(oid),
        "status": "planned",
        "experiment_type": experiment_type,
        "hypothesis_test": str(hyp).strip(),
        "target_population": str(pop).strip(),
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    if measurement_plan is not None:
        exp["measurement_plan"] = measurement_plan
    if success_criteria is not None:
        exp["success_criteria"] = success_criteria
    elif success_threshold is not None:
        exp["success_criteria"] = success_threshold
        exp["success_threshold"] = success_threshold
    if failure_criteria is not None:
        exp["failure_criteria"] = failure_criteria
    if success_threshold is not None and "success_threshold" not in exp:
        exp["success_threshold"] = success_threshold
    if assumptions_tested is not None:
        exp["assumptions_tested"] = list(assumptions_tested)
    elif opportunity.get("assumptions"):
        # link assumption texts by default (not proof they are being tested well)
        exp["assumptions_tested"] = [
            a.get("assumption") if isinstance(a, dict) else str(a)
            for a in opportunity["assumptions"][:5]
        ]
    if duration:
        exp["duration"] = duration
    if observation_window:
        exp["observation_window"] = observation_window
    if channel:
        exp["channel"] = channel
    return exp
