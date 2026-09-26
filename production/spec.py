"""Production Specification builder (Phase 6).

Describes WHAT should be produced. Does not build or deploy.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

PRODUCTION_STATUSES = frozenset({"draft", "ready", "in_progress", "completed"})


def generate_production_id() -> str:
    return f"prd_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_production_ready(
    decision: dict[str, Any] | None,
    opportunity: dict[str, Any] | None,
    experiment: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Deterministic entry gate: only execute + consistent chain."""
    errors: list[str] = []
    if not decision:
        errors.append("decision required")
        return False, errors
    if not opportunity:
        errors.append("opportunity required")
        return False, errors

    verdict = decision.get("verdict") or decision.get("decision")
    if verdict != "execute":
        errors.append(f"decision verdict must be 'execute' (got {verdict!r})")

    if decision.get("opportunity_id") != opportunity.get("id"):
        errors.append("decision/opportunity mismatch")

    eid = decision.get("experiment_id")
    if not eid:
        errors.append("decision missing experiment_id")
    elif experiment is not None:
        if experiment.get("id") != eid:
            errors.append("decision/experiment mismatch")
        if experiment.get("status") != "completed":
            errors.append(f"experiment must be completed (got {experiment.get('status')!r})")
        if experiment.get("opportunity_id") != opportunity.get("id"):
            errors.append("experiment/opportunity mismatch")

    if opportunity.get("status") not in ("building", "shipped"):
        # execute decision advances to building; allow building primarily
        if opportunity.get("status") != "building":
            errors.append(
                f"opportunity status should be 'building' after execute (got {opportunity.get('status')!r})"
            )

    return len(errors) == 0, errors


def build_production_spec(
    *,
    decision: dict[str, Any],
    opportunity: dict[str, Any],
    experiment: dict[str, Any] | None = None,
    production_id: str | None = None,
) -> dict[str, Any]:
    """Build a Production Specification from an execute Decision. No deployment."""
    exp = experiment or {}
    now = _now()
    title = (
        opportunity.get("title")
        or (opportunity.get("problem") or "")[:80]
        or "Untitled production item"
    )
    problem = opportunity.get("problem") or opportunity.get("problem_statement") or ""
    audience = (
        opportunity.get("audience")
        or opportunity.get("target_user")
        or exp.get("target_population")
        or "unspecified"
    )
    assumptions = opportunity.get("assumptions") or []
    if not assumptions and exp.get("assumptions_tested"):
        assumptions = [{"assumption": a, "status": "untested"} for a in exp["assumptions_tested"]]

    # Scope control — minimal, honest when unknown
    core_features = opportunity.get("core_features")
    if not isinstance(core_features, list) or not core_features:
        st = opportunity.get("solution_type") or "unknown"
        core_features = [
            f"Deliver a minimal {st} solution addressing the stated problem",
            "Preserve offline/low-dependency constraints if digital_micro",
        ]

    non_goals = opportunity.get("non_goals")
    if not isinstance(non_goals, list) or not non_goals:
        non_goals = [
            "Do not expand scope beyond the validated experiment hypothesis",
            "Do not claim market size or revenue without evidence",
            "Do not auto-deploy or distribute (Phase 7+)",
        ]

    acceptance = opportunity.get("acceptance_criteria")
    if not isinstance(acceptance, list) or not acceptance:
        acceptance = [
            "Implements the problem focus documented on the Opportunity",
            "Traceable to Decision and Experiment IDs in metadata",
            "Does not include non_goals features",
        ]

    return {
        "id": production_id or generate_production_id(),
        "decision_id": decision["id"],
        "opportunity_id": opportunity["id"],
        "experiment_id": decision.get("experiment_id"),
        "product_name": title,
        "working_title": title,
        "problem": problem,
        "target_user": audience,
        "target_population": exp.get("target_population") or audience,
        "value_proposition": opportunity.get("value_proposition") or "",
        "solution_type": opportunity.get("solution_type") or "unknown",
        "core_features": core_features,
        "non_goals": non_goals,
        "acceptance_criteria": acceptance,
        "evidence_summary": decision.get("evidence_summary") or "",
        "rationale": decision.get("reason") or decision.get("rationale") or "",
        "criteria_snapshot": decision.get("criteria_snapshot") or {},
        "metrics_snapshot": decision.get("metrics_snapshot") or {},
        "source_signal_ids": list(opportunity.get("signal_ids") or []),
        "assumptions": assumptions,
        "unknowns": list(opportunity.get("unknowns") or []),
        "constraints": {
            "solution_type": opportunity.get("solution_type"),
            "geo": opportunity.get("geo"),
            "next_action_from_decision": decision.get("next_action"),
        },
        "production_status": "ready",  # spec ready; does NOT mean deployed
        "created_at": now,
        "updated_at": now,
        "notes": (
            "Phase 6 Production Specification. execute authorizes planning/spec only; "
            "does not build, deploy, or distribute."
        ),
    }
