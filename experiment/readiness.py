"""Deterministic experiment readiness (Phase 4). Not market validation."""
from __future__ import annotations

from typing import Any

from contracts.constants import EXPERIMENT_TYPES
from opportunity.evidence import is_evidence_ready


def is_experiment_ready(
    experiment: dict[str, Any],
    opportunity: dict[str, Any] | None = None,
) -> tuple[bool, list[str]]:
    """Return (ok, errors). Criteria must exist before results — checked separately on mutate."""
    errors: list[str] = []

    oid = experiment.get("opportunity_id")
    if not oid or not str(oid).startswith("opp_"):
        errors.append("valid opportunity_id required")

    if opportunity is None:
        errors.append("opportunity object required for readiness check")
    else:
        if opportunity.get("id") != oid:
            errors.append("experiment.opportunity_id does not match opportunity.id")
        ready, opp_errs = is_evidence_ready(opportunity)
        if not ready:
            errors.append("opportunity not evidence-ready")
            errors.extend(opp_errs)

    hyp = str(experiment.get("hypothesis_test") or "").strip()
    if len(hyp) < 20:
        errors.append("hypothesis_test missing or too short")

    pop = str(experiment.get("target_population") or "").strip()
    if len(pop) < 3:
        errors.append("target_population required")

    et = experiment.get("experiment_type")
    if et not in EXPERIMENT_TYPES:
        errors.append(f"invalid experiment_type: {et!r}")

    plan = experiment.get("measurement_plan")
    if isinstance(plan, str):
        if not plan.strip():
            errors.append("measurement_plan required")
    elif isinstance(plan, dict):
        if len(plan) == 0:
            errors.append("measurement_plan required")
    else:
        errors.append("measurement_plan required (string or object)")

    sc = experiment.get("success_criteria")
    if sc is None and experiment.get("success_threshold") is not None:
        sc = experiment.get("success_threshold")
    if not _nonempty_criteria(sc):
        errors.append("success_criteria required before start")

    fc = experiment.get("failure_criteria")
    if not _nonempty_criteria(fc):
        errors.append("failure_criteria required before start")

    # duration / observation window optional but recommended
    # if present must be non-empty string
    for key in ("duration", "observation_window"):
        if key in experiment and experiment[key] is not None:
            if not str(experiment[key]).strip():
                errors.append(f"{key} must be non-empty when present")

    return len(errors) == 0, errors


def _nonempty_criteria(val: Any) -> bool:
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, dict):
        return len(val) > 0
    return False


def has_recorded_results(experiment: dict[str, Any]) -> bool:
    results = experiment.get("results")
    if isinstance(results, dict) and results:
        return True
    obs = experiment.get("observations")
    if isinstance(obs, list) and len(obs) > 0:
        return True
    return False


def assert_mutable(experiment: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Reject silent changes to frozen fields after results exist."""
    from .constants import IMMUTABLE_AFTER_RESULTS

    if not has_recorded_results(experiment):
        return []
    errors: list[str] = []
    for key in IMMUTABLE_AFTER_RESULTS:
        if key not in proposed:
            continue
        if proposed[key] != experiment.get(key):
            errors.append(
                f"cannot change {key} after results/observations are recorded; create a new experiment"
            )
    return errors
