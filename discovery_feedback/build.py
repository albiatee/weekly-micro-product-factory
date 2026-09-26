"""Build Discovery Feedback / Hint records from LearningRecords."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .constants import FEEDBACK_TYPES


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_hint_id() -> str:
    return f"dh_{uuid.uuid4().hex[:16]}"


def normalize_hint_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def build_hint_from_learning(
    learning: dict[str, Any],
    *,
    created_by: str = "system:discovery_feedback",
    feedback_type: str = "other",
) -> dict[str, Any]:
    oid = learning.get("opportunity_id")
    if not oid:
        raise ValueError("learning missing opportunity_id")
    hint_text = (
        learning.get("next_signals_hint")
        or learning.get("interpretation")
        or learning.get("learning")
        or learning.get("what_failed")
        or "Follow-up discovery candidate from LearningRecord (not market proof)"
    )
    if feedback_type not in FEEDBACK_TYPES:
        feedback_type = "other"
    now = _now()
    h: dict[str, Any] = {
        "id": generate_hint_id(),
        "opportunity_id": oid,
        "hint": str(hint_text).strip(),
        "observation": learning.get("observation")
        or learning.get("what_failed")
        or learning.get("what_worked")
        or "",
        "suggested_action": "Review as discovery candidate; do not treat as validated demand.",
        "rationale": (
            "Derived from LearningRecord only. "
            "Not a claim of proven market demand or revenue."
        ),
        "feedback_type": feedback_type,
        "confidence": learning.get("confidence") or "low",
        "status": "proposed",
        "source_type": "learning_record",
        "source_ids": list(learning.get("source_ids") or [learning.get("id")]),
        "source_learning_id": learning["id"],
        "learning_id": learning["id"],
        "created_at": now,
        "updated_at": now,
        "created_by": created_by,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": None,
        "converted_signal_id": None,
    }
    if learning.get("experiment_id"):
        h["source_experiment_id"] = learning["experiment_id"]
        h["experiment_id"] = learning["experiment_id"]
    if learning.get("decision_id"):
        h["source_decision_id"] = learning["decision_id"]
        h["decision_id"] = learning["decision_id"]
    return h
