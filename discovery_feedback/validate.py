"""Validate Discovery Feedback / Hints."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import FEEDBACK_TYPES, HINT_STATUSES, HINT_TRANSITIONS


@dataclass
class VResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def validate_hint(obj: dict[str, Any]) -> VResult:
    errors: list[str] = []
    if not isinstance(obj, dict):
        return VResult(False, ["hint must be an object"])
    for key in (
        "id",
        "opportunity_id",
        "hint",
        "status",
        "source_learning_id",
        "created_at",
        "updated_at",
    ):
        if key not in obj or not str(obj.get(key) or "").strip():
            errors.append(f"missing or empty: {key}")
    if obj.get("id") and not str(obj["id"]).startswith("dh_"):
        errors.append("id must start with dh_")
    if obj.get("opportunity_id") and not str(obj["opportunity_id"]).startswith("opp_"):
        errors.append("opportunity_id must start with opp_")
    if obj.get("source_learning_id") and not str(obj["source_learning_id"]).startswith("lr_"):
        errors.append("source_learning_id must start with lr_")
    if obj.get("status") and obj["status"] not in HINT_STATUSES:
        errors.append(f"invalid status: {obj.get('status')!r}")
    if obj.get("feedback_type") and obj["feedback_type"] not in FEEDBACK_TYPES:
        errors.append(f"invalid feedback_type: {obj.get('feedback_type')!r}")
    return VResult(ok=len(errors) == 0, errors=errors)


def validate_hint_transition(frm: str, to: str) -> VResult:
    allowed = HINT_TRANSITIONS.get(frm, frozenset())
    if to not in allowed:
        return VResult(
            False,
            [f"illegal transition {frm!r} → {to!r}; allowed: {sorted(allowed) or 'none'}"],
        )
    return VResult(True)
