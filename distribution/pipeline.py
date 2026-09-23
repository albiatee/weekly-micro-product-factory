"""Distribution pipeline — manual plans/actions for shipped Opportunities."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opportunity.store import list_opportunities

from .constants import CHANNELS
from .store import list_actions, list_plans, upsert_action, upsert_plan
from .validate import validate_action, validate_plan, validate_plan_transition


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


@dataclass
class DistResult:
    ok: bool
    plan: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def _resolve_artifact(
    production_ref: dict[str, Any],
    *,
    products_root: Path | None = None,
) -> list[str]:
    """Return errors if artifact cannot be resolved when a path is declared."""
    errors: list[str] = []
    if not production_ref or not isinstance(production_ref, dict):
        return ["production_ref missing or invalid"]
    path = production_ref.get("path")
    if not path:
        return ["production_ref.path missing"]
    # Prefer explicit products_root for tests; else relative to repo
    repo = Path(__file__).resolve().parents[1]
    # path like products/bridge/opp_xxx
    candidate = (products_root / Path(path).name) if products_root else (repo / path)
    # also try products_root as the bridge parent containing opp folders
    if products_root and not candidate.exists():
        candidate = products_root / Path(str(path).rstrip("/").split("/")[-1])
    index_html = candidate / "index.html"
    if not index_html.is_file():
        # soft-fail only when products_root provided (tests); when using real repo path
        if products_root is not None or not (repo / path / "index.html").is_file():
            if not (repo / path / "index.html").is_file() and not index_html.is_file():
                errors.append(f"artifact not found at {path} (expected index.html)")
    return errors


def create_plan(
    opportunity_id: str,
    *,
    channel: str,
    objective: str,
    audience: str | None = None,
    created_by: str = "system:distribution",
    opportunities_root: Path | None = None,
    distribution_root: Path | None = None,
    products_root: Path | None = None,
    require_artifact: bool = True,
    dry_run: bool = False,
) -> DistResult:
    opps = list_opportunities(opportunities_root)
    opp = opps.get(opportunity_id)
    if not opp:
        return DistResult(False, errors=[f"opportunity not found: {opportunity_id}"])
    if opp.get("status") != "shipped":
        return DistResult(
            False,
            errors=[
                f"opportunity status must be 'shipped' (got {opp.get('status')!r})"
            ],
        )
    pref = opp.get("production_ref")
    if not pref:
        return DistResult(False, errors=["opportunity has no production_ref"])

    if channel not in CHANNELS:
        return DistResult(False, errors=[f"invalid channel: {channel!r}"])

    # Idempotency: one active plan per opportunity+channel (not cancelled/completed)
    for p in list_plans(distribution_root).values():
        if (
            p.get("opportunity_id") == opportunity_id
            and p.get("channel") == channel
            and p.get("status") not in ("cancelled", "completed")
        ):
            return DistResult(
                False,
                plan=p,
                errors=[
                    f"active plan already exists for {opportunity_id} channel={channel} "
                    f"({p.get('id')})"
                ],
            )

    if require_artifact:
        art_err = _resolve_artifact(pref, products_root=products_root)
        if art_err:
            return DistResult(False, errors=art_err)

    now = _now()
    plan = {
        "id": _new_id("dist_"),
        "opportunity_id": opportunity_id,
        "production_ref": dict(pref),
        "status": "planned",
        "channel": channel,
        "objective": objective.strip(),
        "audience": (audience or "").strip() or "unspecified",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "results": None,
    }
    if not plan["objective"]:
        return DistResult(False, errors=["objective must be non-empty"])

    vr = validate_plan(plan)
    if not vr.ok:
        return DistResult(False, plan=plan, errors=vr.errors)

    if not dry_run:
        upsert_plan(plan, distribution_root)
    return DistResult(True, plan=plan)


def _get_plan(plan_id: str, root: Path | None) -> dict[str, Any] | None:
    return list_plans(root).get(plan_id)


def _transition(
    plan_id: str,
    to_status: str,
    *,
    distribution_root: Path | None,
    dry_run: bool,
) -> DistResult:
    plan = _get_plan(plan_id, distribution_root)
    if not plan:
        return DistResult(False, errors=[f"plan not found: {plan_id}"])
    tr = validate_plan_transition(plan.get("status", ""), to_status)
    if not tr.ok:
        return DistResult(False, plan=plan, errors=tr.errors)
    plan = {**plan, "status": to_status, "updated_at": _now()}
    vr = validate_plan(plan)
    if not vr.ok:
        return DistResult(False, plan=plan, errors=vr.errors)
    if not dry_run:
        upsert_plan(plan, distribution_root)
    return DistResult(True, plan=plan)


def start_plan(
    plan_id: str, *, distribution_root: Path | None = None, dry_run: bool = False
) -> DistResult:
    plan = _get_plan(plan_id, distribution_root)
    if not plan:
        return DistResult(False, errors=[f"plan not found: {plan_id}"])
    # planned|ready|paused → running
    cur = plan.get("status")
    if cur == "planned":
        # allow planned → running directly per constants
        return _transition(plan_id, "running", distribution_root=distribution_root, dry_run=dry_run)
    if cur == "ready":
        return _transition(plan_id, "running", distribution_root=distribution_root, dry_run=dry_run)
    if cur == "paused":
        return _transition(plan_id, "running", distribution_root=distribution_root, dry_run=dry_run)
    return DistResult(
        False, plan=plan, errors=[f"cannot start from status {cur!r}"]
    )


def pause_plan(
    plan_id: str, *, distribution_root: Path | None = None, dry_run: bool = False
) -> DistResult:
    return _transition(plan_id, "paused", distribution_root=distribution_root, dry_run=dry_run)


def cancel_plan(
    plan_id: str, *, distribution_root: Path | None = None, dry_run: bool = False
) -> DistResult:
    return _transition(plan_id, "cancelled", distribution_root=distribution_root, dry_run=dry_run)


def complete_plan(
    plan_id: str, *, distribution_root: Path | None = None, dry_run: bool = False
) -> DistResult:
    return _transition(plan_id, "completed", distribution_root=distribution_root, dry_run=dry_run)


def record_action(
    plan_id: str,
    *,
    action_type: str,
    notes: str | None = None,
    status: str = "executed",
    distribution_root: Path | None = None,
    dry_run: bool = False,
) -> DistResult:
    plan = _get_plan(plan_id, distribution_root)
    if not plan:
        return DistResult(False, errors=[f"plan not found: {plan_id}"])
    if plan.get("status") not in ("running", "ready", "planned"):
        return DistResult(
            False,
            plan=plan,
            errors=[f"cannot record action when plan status is {plan.get('status')!r}"],
        )

    # Idempotency: same plan + action_type + notes fingerprint while executed exists
    for a in list_actions(distribution_root).values():
        if (
            a.get("distribution_id") == plan_id
            and a.get("action_type") == action_type
            and a.get("status") == "executed"
            and (a.get("notes") or "") == (notes or "")
        ):
            return DistResult(
                False,
                plan=plan,
                action=a,
                errors=["duplicate action: same plan, action_type, and notes already executed"],
            )

    now = _now()
    action = {
        "id": _new_id("dact_"),
        "distribution_id": plan_id,
        "channel": plan.get("channel"),
        "action_type": action_type,
        "status": status,
        "created_at": now,
        "executed_at": now if status == "executed" else None,
        "result": None,
        "notes": notes or "",
    }
    vr = validate_action(action)
    if not vr.ok:
        return DistResult(False, plan=plan, action=action, errors=vr.errors)

    if not dry_run:
        upsert_action(action, distribution_root)
    return DistResult(True, plan=plan, action=action)


def record_result(
    plan_id: str,
    *,
    metrics: dict[str, Any] | None = None,
    qualitative_notes: list[str] | None = None,
    distribution_root: Path | None = None,
    dry_run: bool = False,
) -> DistResult:
    """Record operator-supplied results only — no fabricated metrics."""
    plan = _get_plan(plan_id, distribution_root)
    if not plan:
        return DistResult(False, errors=[f"plan not found: {plan_id}"])

    results: dict[str, Any] = dict(plan.get("results") or {})
    if metrics is not None:
        if not isinstance(metrics, dict):
            return DistResult(False, plan=plan, errors=["metrics must be an object"])
        # do not invent keys — store as supplied
        results["metrics"] = metrics
    if qualitative_notes is not None:
        results["qualitative_notes"] = list(qualitative_notes)
    if not results:
        return DistResult(False, plan=plan, errors=["no results provided"])

    plan = {**plan, "results": results, "updated_at": _now()}
    if not dry_run:
        upsert_plan(plan, distribution_root)
    return DistResult(True, plan=plan)
