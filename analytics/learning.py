"""Build evidence-based LearningRecords (Phase 1 contract) — no auto decisions."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from contracts.validate import validate_learning_record


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_learning_id() -> str:
    return f"lr_{uuid.uuid4().hex[:16]}"


def build_learning_for_opportunity(
    opportunity: dict[str, Any],
    *,
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    distribution_plans: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Create one LearningRecord from available evidence only.

    Returns None if insufficient linked evidence (no completed experiment and no decision).
    """
    oid = opportunity.get("id")
    if not oid:
        return None

    related_exp = [e for e in experiments.values() if e.get("opportunity_id") == oid]
    related_dec = [d for d in decisions.values() if d.get("opportunity_id") == oid]
    related_plans = [p for p in distribution_plans.values() if p.get("opportunity_id") == oid]

    completed = [e for e in related_exp if e.get("status") == "completed"]
    if not completed and not related_dec:
        return None

    what_worked: list[str] = []
    what_failed: list[str] = []
    commercial_notes: list[str] = []
    score_notes: list[str] = []
    hints: list[str] = []

    for e in completed:
        res = e.get("results") or {}
        metrics = res.get("metrics") if isinstance(res, dict) else None
        notes = res.get("qualitative_notes") if isinstance(res, dict) else None
        passed = res.get("passed") if isinstance(res, dict) else None
        line = f"Experiment {e.get('id')} ({e.get('experiment_type')}) status=completed"
        if metrics:
            line += f" operator_metrics={metrics}"
        if notes:
            line += f" notes={notes}"
        if passed is True:
            what_worked.append(line + " (operator marked passed=true — not automatic market proof)")
        elif passed is False:
            what_failed.append(line + " (operator marked passed=false)")
        else:
            what_worked.append(line + " (results recorded; pass flag absent)")

    for e in related_exp:
        if e.get("status") == "aborted":
            what_failed.append(
                f"Experiment {e.get('id')} aborted"
                + (f": {(e.get('results') or {}).get('qualitative_notes', [])}" if e.get("results") else "")
            )

    for d in related_dec:
        what_worked.append(
            f"Decision {d.get('id')} verdict={d.get('verdict')} reason={d.get('reason')!r}"
        )

    for p in related_plans:
        res = p.get("results") or {}
        if isinstance(res, dict) and (res.get("metrics") or res.get("qualitative_notes")):
            commercial_notes.append(
                f"Distribution plan {p.get('id')} channel={p.get('channel')} "
                f"operator_results metrics={res.get('metrics')} notes={res.get('qualitative_notes')} "
                f"(not inferred revenue)"
            )

    score = opportunity.get("score")
    if isinstance(score, dict) and score.get("total") is not None:
        score_notes.append(
            f"Prior opportunity score.total={score.get('total')} was a prioritization heuristic; "
            f"compare only against recorded experiment/distribution results — score was not modified."
        )

    if opportunity.get("problem"):
        hints.append(
            f"Investigate whether similar signals still mention: "
            f"{str(opportunity['problem'])[:120]}"
        )
    if not hints:
        hints.append("Review linked signals for recurring unmet needs (hint only — no Signal created).")

    if not what_worked and not what_failed:
        what_worked.append("Insufficient structured outcomes; see linked entities.")

    exp_id = completed[0]["id"] if completed else None
    dec_id = related_dec[0]["id"] if related_dec else None

    worked_s = " | ".join(what_worked) if what_worked else "No explicit success notes in stored evidence."
    failed_s = " | ".join(what_failed) if what_failed else "None recorded as explicit failure in stored evidence."
    lr: dict[str, Any] = {
        "id": generate_learning_id(),
        "opportunity_id": oid,
        "what_worked": worked_s,
        "what_failed": failed_s,
        "created_at": _now(),
    }
    if exp_id:
        lr["experiment_id"] = exp_id
    if dec_id:
        lr["decision_id"] = dec_id
    lr["next_signals_hint"] = " | ".join(hints)
    if score_notes:
        lr["score_calibration_notes"] = " ".join(score_notes)
    if commercial_notes:
        lr["commercial_notes"] = " ".join(commercial_notes)

    vr = validate_learning_record(lr)
    if not vr.ok:
        return None
    return lr
