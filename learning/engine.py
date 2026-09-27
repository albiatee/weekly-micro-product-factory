"""Deterministic learning from analytics records — no causal invention."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analytics.records import get_analytics_record, list_analytics_records
from analytics.store import load_index, save_index, upsert_learning

from .models import observation

ROOT = Path(__file__).resolve().parents[1]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lr_id() -> str:
    return f"lr_{uuid.uuid4().hex[:16]}"


@dataclass
class LearningResult:
    ok: bool
    learning: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def list_learning_records(root: Path | None = None) -> dict[str, dict[str, Any]]:
    data = load_index(root)
    raw = data.get("learnings")
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, dict)}
    return {}


def generate_learning_from_analytics(
    analytics_id: str,
    *,
    analytics_root: Path | None = None,
    dry_run: bool = False,
) -> LearningResult:
    """Build learning record from a single analytics record.

    Observed/derived only. No causal claims without experiment linkage (inferred forbidden by default).
    """
    rec = get_analytics_record(analytics_id, analytics_root)
    if not rec:
        return LearningResult(False, errors=[f"analytics not found: {analytics_id}"])

    observations: list[dict[str, Any]] = []
    lessons: list[str] = []
    confidence = "low"

    if rec.get("status") == "not_available":
        observations.append(
            observation(
                kind="unknown",
                statement="No product metrics available for this build/period.",
                evidence={"analytics_id": analytics_id, "status": "not_available"},
            )
        )
        lessons.append(
            "Cannot draw product-performance lessons without supplied metrics."
        )
        confidence = "none"
    else:
        raw = (rec.get("metrics") or {}).get("raw") or {}
        derived = (rec.get("metrics") or {}).get("derived") or {}

        for key, val in raw.items():
            observations.append(
                observation(
                    kind="observed",
                    statement=f"Recorded {key}={val}.",
                    evidence={"metric": key, "value": val},
                )
            )

        for key, val in derived.items():
            if val is None:
                observations.append(
                    observation(
                        kind="unknown",
                        statement=f"Derived metric {key} not computable (missing or invalid inputs).",
                        evidence={"metric": key},
                    )
                )
            else:
                observations.append(
                    observation(
                        kind="derived",
                        statement=f"Computed {key}={val}.",
                        evidence={"metric": key, "value": val},
                    )
                )

        # Conservative lessons — descriptive only, not causal
        signup_rate = derived.get("signup_rate")
        if signup_rate is not None:
            if signup_rate >= 0.1:
                lessons.append(
                    f"Observed signup_rate={signup_rate} (derived from supplied visits/signups)."
                )
                confidence = "medium"
            elif signup_rate == 0:
                lessons.append(
                    "Observed signup_rate=0 from supplied metrics; interest signal absent in this period."
                )
                confidence = "medium"
            else:
                lessons.append(
                    f"Observed low signup_rate={signup_rate}; not a causal claim about design or channel."
                )
                confidence = "low"
        elif not raw:
            lessons.append("Empty raw metrics after validation.")
            confidence = "none"
        else:
            lessons.append(
                "Raw metrics recorded; insufficient pairs for rate derivation or no visits>0."
            )
            confidence = "low"

    lr = {
        "id": _lr_id(),
        "source_analytics_id": analytics_id,
        "build_id": rec.get("build_id"),
        "opportunity_id": rec.get("opportunity_id"),
        "product_id": rec.get("product_id"),
        "observations": observations,
        "lessons": lessons,
        "confidence": confidence,
        "created_at": _now(),
        "advisory": True,
        "note": "Learning is informational; does not approve/reject future ideas.",
    }

    if not dry_run:
        upsert_learning(lr, analytics_root)
    return LearningResult(True, learning=lr)
