"""Phase 7 — create Distribution from Production Specification (no external publish)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from decision.store import list_decisions
from experiment.store import list_experiments
from opportunity.store import list_opportunities
from production.store import list_production_specs

from .constants import CHANNELS, DISTRIBUTION_TYPES
from .store import list_plans, upsert_plan
from .validate import validate_plan

ACTIVE_STATUSES = frozenset({"planned", "prepared", "ready", "running", "paused"})


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return f"dist_{uuid.uuid4().hex[:16]}"


def is_distribution_ready(
    production_spec: dict[str, Any] | None,
    decision: dict[str, Any] | None,
    opportunity: dict[str, Any] | None,
    experiment: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not production_spec:
        errors.append("production_spec required")
        return False, errors
    if production_spec.get("production_status") not in ("ready", "in_progress", "completed"):
        errors.append(
            f"production_spec status must be ready/in_progress/completed "
            f"(got {production_spec.get('production_status')!r})"
        )

    if not decision:
        errors.append("decision required")
    else:
        verdict = decision.get("verdict") or decision.get("decision")
        if verdict != "execute":
            errors.append(f"decision must be execute (got {verdict!r})")
        if decision.get("id") != production_spec.get("decision_id"):
            errors.append("production_spec/decision mismatch")

    if not opportunity:
        errors.append("opportunity required")
    else:
        if opportunity.get("id") != production_spec.get("opportunity_id"):
            errors.append("production_spec/opportunity mismatch")
        if opportunity.get("status") not in ("building", "shipped"):
            errors.append(
                f"opportunity status should be building or shipped "
                f"(got {opportunity.get('status')!r})"
            )

    if not experiment:
        errors.append("experiment required")
    else:
        if experiment.get("id") != production_spec.get("experiment_id"):
            errors.append("production_spec/experiment mismatch")
        if experiment.get("status") != "completed":
            errors.append(f"experiment must be completed (got {experiment.get('status')!r})")

    return len(errors) == 0, errors


def create_distribution_from_spec(
    production_spec_id: str,
    *,
    channel: str,
    distribution_type: str = "plan",
    audience: str | None = None,
    message: str | None = None,
    destination_url: str | None = None,
    objective: str | None = None,
    created_by: str = "system:distribution",
    production_root: Path | None = None,
    decisions_root: Path | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    distribution_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a Distribution plan record from a Production Spec.

    Returns {"ok": bool, "plan": dict|None, "errors": list}.
    Status starts as **planned** — never auto-published. No network I/O.
    """
    specs = list_production_specs(production_root)
    decisions = list_decisions(decisions_root)
    opportunities = list_opportunities(opportunities_root)
    experiments = list_experiments(experiments_root)

    spec = specs.get(production_spec_id)
    if not spec:
        return {"ok": False, "plan": None, "errors": [f"production_spec not found: {production_spec_id}"]}

    if channel not in CHANNELS:
        return {"ok": False, "plan": None, "errors": [f"invalid channel: {channel!r}"]}
    if distribution_type not in DISTRIBUTION_TYPES:
        return {"ok": False, "plan": None, "errors": [f"invalid distribution_type: {distribution_type!r}"]}

    dec = decisions.get(spec.get("decision_id"))
    opp = opportunities.get(spec.get("opportunity_id"))
    exp = experiments.get(spec.get("experiment_id"))

    ready, errs = is_distribution_ready(spec, dec, opp, exp)
    if not ready:
        return {"ok": False, "plan": None, "errors": errs}

    # Idempotency: one active plan per production_spec + channel
    for p in list_plans(distribution_root).values():
        if (
            p.get("production_spec_id") == production_spec_id
            and p.get("channel") == channel
            and p.get("status") in ACTIVE_STATUSES
        ):
            return {
                "ok": False,
                "plan": p,
                "errors": [
                    f"active distribution already exists for spec {production_spec_id} "
                    f"channel={channel} ({p.get('id')})"
                ],
            }

    now = _now()
    plan = {
        "id": _new_id(),
        "production_spec_id": production_spec_id,
        "decision_id": spec.get("decision_id"),
        "opportunity_id": spec.get("opportunity_id"),
        "experiment_id": spec.get("experiment_id"),
        "product_name": spec.get("product_name") or spec.get("working_title"),
        "channel": channel,
        "distribution_type": distribution_type,
        "audience": (audience or spec.get("target_user") or "unspecified").strip(),
        "message": (message or "").strip() or None,
        "message_status": "draft" if message else None,  # not published
        "destination_url": destination_url,
        "status": "planned",  # NOT published
        "objective": (objective or f"Distribute {spec.get('product_name') or 'product'} via {channel}").strip(),
        "source_signal_ids": list(spec.get("source_signal_ids") or []),
        "publication": None,  # filled only via explicit record_publication
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "results": None,
        "notes": (
            "Phase 7 distribution plan. Creation does not mean published. "
            "No external network calls."
        ),
    }

    vr = validate_plan(plan)
    if not vr.ok:
        return {"ok": False, "plan": plan, "errors": vr.errors}

    if not dry_run:
        upsert_plan(plan, distribution_root)
    return {"ok": True, "plan": plan, "errors": []}


def prepare_distribution(
    plan_id: str,
    *,
    message: str | None = None,
    distribution_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """planned → prepared. Still not published."""
    plans = list_plans(distribution_root)
    plan = plans.get(plan_id)
    if not plan:
        return {"ok": False, "plan": None, "errors": [f"plan not found: {plan_id}"]}
    if plan.get("status") not in ("planned", "ready"):
        return {
            "ok": False,
            "plan": plan,
            "errors": [f"cannot prepare from status {plan.get('status')!r}"],
        }
    updated = {
        **plan,
        "status": "prepared",
        "updated_at": _now(),
    }
    if message is not None:
        updated["message"] = message
        updated["message_status"] = "prepared"
    if not dry_run:
        upsert_plan(updated, distribution_root)
    return {"ok": True, "plan": updated, "errors": []}


def record_publication(
    plan_id: str,
    *,
    success: bool,
    destination_url: str | None = None,
    notes: str | None = None,
    metrics: dict[str, Any] | None = None,
    distribution_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Explicit publication result. No network — operator reports outcome."""
    plans = list_plans(distribution_root)
    plan = plans.get(plan_id)
    if not plan:
        return {"ok": False, "plan": None, "errors": [f"plan not found: {plan_id}"]}
    if plan.get("status") not in ("planned", "prepared", "ready", "running"):
        return {
            "ok": False,
            "plan": plan,
            "errors": [f"cannot record publication from status {plan.get('status')!r}"],
        }
    status = "published" if success else "failed"
    pub = {
        "success": success,
        "recorded_at": _now(),
        "destination_url": destination_url or plan.get("destination_url"),
        "notes": notes,
        "metrics": metrics or {},
        "source": "manual_operator_report",
    }
    updated = {
        **plan,
        "status": status,
        "publication": pub,
        "message_status": "published" if success else plan.get("message_status"),
        "updated_at": _now(),
        "results": {"publication": pub},
    }
    if not dry_run:
        upsert_plan(updated, distribution_root)
    return {"ok": True, "plan": updated, "errors": []}
