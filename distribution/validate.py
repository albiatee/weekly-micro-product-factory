"""Deterministic validation for Distribution plans and actions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import (
    ACTION_STATUSES,
    ACTION_TYPES,
    CHANNELS,
    PLAN_STATUSES,
    PLAN_TRANSITIONS,
)


@dataclass
class VResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_plan(obj: dict[str, Any]) -> VResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return VResult(False, ["plan must be an object"])
    for key in (
        "id",
        "opportunity_id",
        "status",
        "channel",
        "objective",
        "created_by",
        "created_at",
        "updated_at",
    ):
        if key not in obj or not str(obj.get(key) or "").strip():
            errors.append(f"missing or empty required field: {key}")
    if obj.get("id") and not str(obj["id"]).startswith("dist_"):
        errors.append("id must start with dist_")
    if obj.get("opportunity_id") and not str(obj["opportunity_id"]).startswith("opp_"):
        errors.append("opportunity_id must start with opp_")
    if obj.get("status") and obj["status"] not in PLAN_STATUSES:
        errors.append(f"invalid status: {obj.get('status')!r}")
    if obj.get("channel") and obj["channel"] not in CHANNELS:
        errors.append(f"invalid channel: {obj.get('channel')!r}")
    return VResult(ok=len(errors) == 0, errors=errors)


def validate_plan_transition(frm: str, to: str) -> VResult:
    errors: list[str] = []
    allowed = PLAN_TRANSITIONS.get(frm, frozenset())
    if to not in allowed:
        errors.append(
            f"illegal plan transition {frm!r} → {to!r}; allowed: {sorted(allowed) or 'none'}"
        )
    return VResult(ok=len(errors) == 0, errors=errors)


def validate_action(obj: dict[str, Any]) -> VResult:
    errors: list[str] = []
    for key in ("id", "distribution_id", "channel", "action_type", "status", "created_at"):
        if key not in obj or not str(obj.get(key) or "").strip():
            errors.append(f"missing or empty required field: {key}")
    if obj.get("id") and not str(obj["id"]).startswith("dact_"):
        errors.append("id must start with dact_")
    if obj.get("distribution_id") and not str(obj["distribution_id"]).startswith("dist_"):
        errors.append("distribution_id must start with dist_")
    if obj.get("channel") and obj["channel"] not in CHANNELS:
        errors.append(f"invalid channel: {obj.get('channel')!r}")
    if obj.get("action_type") and obj["action_type"] not in ACTION_TYPES:
        errors.append(f"invalid action_type: {obj.get('action_type')!r}")
    if obj.get("status") and obj["status"] not in ACTION_STATUSES:
        errors.append(f"invalid action status: {obj.get('status')!r}")
    return VResult(ok=len(errors) == 0, errors=errors)
