"""Build Discovery Hint from LearningRecord (no fabrication)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any


def generate_hint_id() -> str:
    return f"dh_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_hint_text(text: str) -> str:
    t = (text or "").strip().lower()
    return re.sub(r"\s+", " ", t)


def build_hint_from_learning(
    learning: dict[str, Any],
    *,
    created_by: str = "system:discovery_feedback",
) -> dict[str, Any]:
    """Use next_signals_hint only — do not invent market claims."""
    hint_text = (learning.get("next_signals_hint") or "").strip()
    if not hint_text:
        raise ValueError("LearningRecord has no next_signals_hint; refuse to invent a hint")

    now = _now()
    h: dict[str, Any] = {
        "id": generate_hint_id(),
        "opportunity_id": learning["opportunity_id"],
        "hint": hint_text,
        "status": "proposed",
        "source_learning_id": learning["id"],
        "created_at": now,
        "updated_at": now,
        "created_by": created_by,
        "rationale": (
            "Derived from LearningRecord.next_signals_hint only. "
            "Not a claim of proven market demand or revenue."
        ),
    }
    if learning.get("experiment_id"):
        h["source_experiment_id"] = learning["experiment_id"]
    if learning.get("decision_id"):
        h["source_decision_id"] = learning["decision_id"]
    return h
