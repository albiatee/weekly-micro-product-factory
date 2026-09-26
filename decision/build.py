"""Build Decision records (no automatic verdict from scores)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

# Suggested next actions by verdict — guidance only, not automatic execution.
DEFAULT_NEXT_ACTION = {
    "execute": "prepare production specification (Phase 6 owns production)",
    "iterate": "revise hypothesis or offer and run another experiment",
    "kill": "archive opportunity and stop current hypothesis",
}


def generate_decision_id() -> str:
    return f"dec_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def criteria_snapshot_from_experiment(exp: dict[str, Any]) -> dict[str, Any]:
    """Freeze the predefined criteria used for the decision (pre-results)."""
    snap: dict[str, Any] = {
        "hypothesis_test": exp.get("hypothesis_test"),
        "measurement_plan": exp.get("measurement_plan"),
        "success_criteria": exp.get("success_criteria") or exp.get("success_threshold"),
        "failure_criteria": exp.get("failure_criteria"),
        "target_population": exp.get("target_population"),
        "experiment_type": exp.get("experiment_type"),
    }
    if exp.get("success_threshold") is not None and "success_threshold" not in snap:
        snap["success_threshold"] = exp.get("success_threshold")
    return snap


def metrics_snapshot_from_experiment(exp: dict[str, Any]) -> dict[str, Any]:
    """Record observed results without interpreting them as market truth."""
    results = exp.get("results") if isinstance(exp.get("results"), dict) else {}
    return {
        "results": results,
        "observations": list(exp.get("observations") or []),
        "experiment_status": exp.get("status"),
    }


def evidence_summary_from_experiment(exp: dict[str, Any]) -> str:
    results = exp.get("results") if isinstance(exp.get("results"), dict) else {}
    metrics = results.get("metrics") if isinstance(results.get("metrics"), dict) else {}
    parts = [
        f"experiment={exp.get('id')}",
        f"type={exp.get('experiment_type')}",
        f"status={exp.get('status')}",
    ]
    if metrics:
        parts.append("metrics=" + ", ".join(f"{k}={v}" for k, v in metrics.items()))
    notes = results.get("qualitative_notes")
    if notes:
        parts.append(f"notes={notes!r}")
    if results.get("passed") is not None:
        parts.append(f"observational_passed={results.get('passed')}")
    return "; ".join(parts)


def build_decision(
    *,
    opportunity_id: str,
    verdict: str,
    reason: str,
    evidence_refs: list[str],
    decided_by: str,
    experiment_id: str,
    experiment: dict[str, Any] | None = None,
    next_action: str | None = None,
    agent_suggestion: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    if not experiment_id:
        raise ValueError("experiment_id is required for Decision")

    exp = experiment or {}
    now = _now()
    action = (next_action or "").strip() or DEFAULT_NEXT_ACTION.get(verdict, "review decision record")

    dec: dict[str, Any] = {
        "id": decision_id or generate_decision_id(),
        "opportunity_id": opportunity_id,
        "experiment_id": experiment_id,
        "verdict": verdict,
        "decision": verdict,  # alias for Phase 5 vocabulary
        "reason": (reason or "").strip(),
        "rationale": (reason or "").strip(),  # alias
        "evidence_refs": list(evidence_refs or []),
        "decided_by": decided_by,
        "decided_at": now,
        "created_at": now,
        "criteria_snapshot": criteria_snapshot_from_experiment(exp) if exp else {},
        "metrics_snapshot": metrics_snapshot_from_experiment(exp) if exp else {},
        "evidence_summary": evidence_summary_from_experiment(exp) if exp else "",
        "assumptions_affected": list(exp.get("assumptions_tested") or []),
        "next_action": action,
    }
    if agent_suggestion:
        dec["agent_suggestion"] = agent_suggestion
    return dec
