"""Validation experiment pipeline — create, start, record, complete, abort."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.validate import validate_experiment, validate_opportunity, validate_opportunity_transition

from opportunity.evidence import is_evidence_ready
from .readiness import assert_mutable, has_recorded_results, is_experiment_ready
from opportunity.store import list_opportunities, upsert_opportunity

from .build import build_experiment
from .lifecycle import validate_experiment_transition
from .store import get_experiment, list_experiments, upsert_experiment


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ExpOpResult:
    ok: bool
    experiment: dict[str, Any] | None = None
    opportunity: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def _load_opportunity(
    opportunity_id: str, opportunities_root: Path | None
) -> dict[str, Any] | None:
    opps = list_opportunities(opportunities_root)
    return opps.get(opportunity_id)


def create_experiment(
    opportunity_id: str,
    *,
    experiment_type: str,
    hypothesis_test: str | None = None,
    measurement_plan: str | dict[str, Any] | None = None,
    success_threshold: dict[str, Any] | None = None,
    success_criteria: str | dict[str, Any] | None = None,
    failure_criteria: str | dict[str, Any] | None = None,
    target_population: str | None = None,
    assumptions_tested: list[str] | None = None,
    duration: str | None = None,
    observation_window: str | None = None,
    channel: str | None = None,
    created_by: str = "system:experiment_engine",
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    dry_run: bool = False,
) -> ExpOpResult:
    opp = _load_opportunity(opportunity_id, opportunities_root)
    if not opp:
        return ExpOpResult(False, errors=[f"opportunity not found: {opportunity_id}"])

    try:
        exp = build_experiment(
            opp,
            experiment_type=experiment_type,
            hypothesis_test=hypothesis_test,
            measurement_plan=measurement_plan,
            success_threshold=success_threshold,
            success_criteria=success_criteria,
            failure_criteria=failure_criteria,
            target_population=target_population,
            assumptions_tested=assumptions_tested,
            duration=duration,
            observation_window=observation_window,
            channel=channel,
            created_by=created_by,
        )
    except ValueError as e:
        return ExpOpResult(False, errors=[str(e)])

    vr = validate_experiment(exp)
    if not vr.ok:
        return ExpOpResult(False, experiment=exp, errors=vr.errors)

    if not dry_run:
        upsert_experiment(exp, experiments_root)
    return ExpOpResult(True, experiment=exp, opportunity=opp)


def start_experiment(
    experiment_id: str,
    *,
    measurement_plan: str | dict[str, Any] | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    dry_run: bool = False,
) -> ExpOpResult:
    """planned → running; sync Opportunity to experimenting + active_experiment_id."""
    exp = get_experiment(experiment_id, experiments_root)
    if not exp:
        return ExpOpResult(False, errors=[f"experiment not found: {experiment_id}"])

    tr = validate_experiment_transition(exp.get("status", ""), "running")
    if not tr.ok:
        return ExpOpResult(False, experiment=exp, errors=tr.errors)

    if measurement_plan is not None:
        exp = {**exp, "measurement_plan": measurement_plan}
    elif not exp.get("measurement_plan"):
        return ExpOpResult(
            False,
            experiment=exp,
            errors=["measurement_plan required before/at running"],
        )

    exp = {
        **exp,
        "status": "running",
        "updated_at": _now(),
        "start_at": exp.get("start_at") or _now(),
    }
    vr = validate_experiment(exp)
    if not vr.ok:
        return ExpOpResult(False, experiment=exp, errors=vr.errors)

    opp = _load_opportunity(exp["opportunity_id"], opportunities_root)
    if not opp:
        return ExpOpResult(
            False,
            experiment=exp,
            errors=[f"opportunity not found: {exp['opportunity_id']}"],
        )

    # Phase 3: evidence readiness before moving opportunity to experimenting
    ready, ready_errs = is_evidence_ready(opp)
    if not ready:
        return ExpOpResult(
            False,
            experiment=exp,
            opportunity=opp,
            errors=["opportunity not evidence-ready"] + ready_errs,
        )

    # Phase 4: experiment readiness (criteria predefined)
    exp_ready, exp_errs = is_experiment_ready(exp, opp)
    if not exp_ready:
        return ExpOpResult(
            False,
            experiment=exp,
            opportunity=opp,
            errors=["experiment not ready"] + exp_errs,
        )

    # Phase 4: one active running experiment per opportunity
    active = [
        e
        for e in list_experiments(experiments_root).values()
        if e.get("opportunity_id") == opp.get("id")
        and e.get("status") == "running"
        and e.get("id") != exp.get("id")
    ]
    if active:
        return ExpOpResult(
            False,
            experiment=exp,
            opportunity=opp,
            errors=[
                f"opportunity already has active running experiment: {active[0].get('id')}"
            ],
        )

    # hypothesized → experimenting (or already experimenting)
    if opp.get("status") == "hypothesized":
        tr_opp = validate_opportunity_transition("hypothesized", "experimenting")
        if not tr_opp.ok:
            return ExpOpResult(False, experiment=exp, opportunity=opp, errors=tr_opp.errors)
        opp = {
            **opp,
            "status": "experimenting",
            "active_experiment_id": exp["id"],
            "updated_at": _now(),
        }
    elif opp.get("status") == "experimenting":
        opp = {
            **opp,
            "active_experiment_id": exp["id"],
            "updated_at": _now(),
        }
    else:
        return ExpOpResult(
            False,
            experiment=exp,
            opportunity=opp,
            errors=[
                f"opportunity status {opp.get('status')!r} cannot start experiment "
                f"(expected hypothesized or experimenting)"
            ],
        )

    vr_opp = validate_opportunity(opp)
    if not vr_opp.ok:
        return ExpOpResult(False, experiment=exp, opportunity=opp, errors=vr_opp.errors)

    if not dry_run:
        upsert_experiment(exp, experiments_root)
        upsert_opportunity(opp, opportunities_root)

    return ExpOpResult(True, experiment=exp, opportunity=opp)


def record_results(
    experiment_id: str,
    *,
    metrics: dict[str, Any] | None = None,
    qualitative_notes: list[str] | None = None,
    passed: bool | None = None,
    observations: list[dict[str, Any]] | None = None,
    experiments_root: Path | None = None,
    dry_run: bool = False,
) -> ExpOpResult:
    """Attach results/observations to a running experiment — no fabricated metrics.

    Does NOT decide execute/iterate/kill (Phase 5).
    Recording results freezes hypothesis/criteria (immutability).
    """
    exp = get_experiment(experiment_id, experiments_root)
    if not exp:
        return ExpOpResult(False, errors=[f"experiment not found: {experiment_id}"])

    if exp.get("status") not in ("running", "planned"):
        return ExpOpResult(
            False,
            experiment=exp,
            errors=[f"cannot record results when status is {exp.get('status')!r}"],
        )

    results: dict[str, Any] = dict(exp.get("results") or {})
    obs_list: list[dict[str, Any]] = list(exp.get("observations") or [])
    now = _now()

    if metrics is not None:
        if not isinstance(metrics, dict):
            return ExpOpResult(False, experiment=exp, errors=["metrics must be an object"])
        results["metrics"] = metrics
        for k, v in metrics.items():
            obs_list.append(
                {
                    "metric": str(k),
                    "value": v,
                    "source": "manual_entry",
                    "captured_at": now,
                }
            )
    if qualitative_notes is not None:
        results["qualitative_notes"] = list(qualitative_notes)
        for note in qualitative_notes:
            obs_list.append(
                {
                    "metric": "note",
                    "value": note,
                    "source": "manual_entry",
                    "captured_at": now,
                }
            )
    if observations is not None:
        for o in observations:
            if not isinstance(o, dict) or "metric" not in o:
                return ExpOpResult(
                    False, experiment=exp, errors=["each observation needs metric"]
                )
            row = dict(o)
            row.setdefault("captured_at", now)
            row.setdefault("source", "manual_entry")
            obs_list.append(row)
            results.setdefault("metrics", {})
            if isinstance(results["metrics"], dict) and "value" in row:
                results["metrics"][str(row["metric"])] = row["value"]
    if passed is not None:
        # observational flag only — not a Decision verdict
        results["passed"] = bool(passed)

    if not results and not obs_list:
        return ExpOpResult(False, experiment=exp, errors=["no results provided"])

    exp = {
        **exp,
        "results": results,
        "observations": obs_list,
        "updated_at": now,
    }
    if not dry_run:
        upsert_experiment(exp, experiments_root)
    return ExpOpResult(True, experiment=exp)


def update_experiment_fields(
    experiment_id: str,
    fields: dict[str, Any],
    *,
    experiments_root: Path | None = None,
    dry_run: bool = False,
) -> ExpOpResult:
    """Update experiment fields with immutability after results."""
    exp = get_experiment(experiment_id, experiments_root)
    if not exp:
        return ExpOpResult(False, errors=[f"experiment not found: {experiment_id}"])
    if exp.get("status") in ("completed", "aborted"):
        return ExpOpResult(False, experiment=exp, errors=["cannot update terminal experiment"])
    errs = assert_mutable(exp, fields)
    if errs:
        return ExpOpResult(False, experiment=exp, errors=errs)
    exp = {**exp, **fields, "updated_at": _now()}
    vr = validate_experiment(exp)
    if not vr.ok:
        return ExpOpResult(False, experiment=exp, errors=vr.errors)
    if not dry_run:
        upsert_experiment(exp, experiments_root)
    return ExpOpResult(True, experiment=exp)


def complete_experiment(
    experiment_id: str,
    *,
    experiments_root: Path | None = None,
    opportunities_root: Path | None = None,
    dry_run: bool = False,
) -> ExpOpResult:
    """running → completed. Requires results. Does NOT create Decision."""
    exp = get_experiment(experiment_id, experiments_root)
    if not exp:
        return ExpOpResult(False, errors=[f"experiment not found: {experiment_id}"])

    tr = validate_experiment_transition(exp.get("status", ""), "completed")
    if not tr.ok:
        return ExpOpResult(False, experiment=exp, errors=tr.errors)

    results = exp.get("results")
    if not isinstance(results, dict) or not results:
        return ExpOpResult(
            False,
            experiment=exp,
            errors=["cannot complete without recorded results"],
        )
    # Need at least metrics or qualitative_notes
    has_metrics = isinstance(results.get("metrics"), dict) and len(results["metrics"]) > 0
    has_notes = isinstance(results.get("qualitative_notes"), list) and len(
        results["qualitative_notes"]
    ) > 0
    if not has_metrics and not has_notes:
        return ExpOpResult(
            False,
            experiment=exp,
            errors=["results must include non-empty metrics and/or qualitative_notes"],
        )

    exp = {
        **exp,
        "status": "completed",
        "updated_at": _now(),
        "end_at": _now(),
    }
    vr = validate_experiment(exp)
    if not vr.ok:
        return ExpOpResult(False, experiment=exp, errors=vr.errors)

    if not dry_run:
        upsert_experiment(exp, experiments_root)
    # Opportunity stays experimenting — Phase 5 will decide
    opp = _load_opportunity(exp["opportunity_id"], opportunities_root)
    return ExpOpResult(True, experiment=exp, opportunity=opp)


def abort_experiment(
    experiment_id: str,
    *,
    reason: str | None = None,
    experiments_root: Path | None = None,
    opportunities_root: Path | None = None,
    dry_run: bool = False,
) -> ExpOpResult:
    """planned|running → aborted. Does NOT kill Opportunity."""
    exp = get_experiment(experiment_id, experiments_root)
    if not exp:
        return ExpOpResult(False, errors=[f"experiment not found: {experiment_id}"])

    tr = validate_experiment_transition(exp.get("status", ""), "aborted")
    if not tr.ok:
        return ExpOpResult(False, experiment=exp, errors=tr.errors)

    notes = list((exp.get("results") or {}).get("qualitative_notes") or [])
    if reason:
        notes.append(f"aborted: {reason}")
    results = dict(exp.get("results") or {})
    if notes:
        results["qualitative_notes"] = notes

    exp = {
        **exp,
        "status": "aborted",
        "updated_at": _now(),
        "end_at": _now(),
    }
    if results:
        exp["results"] = results

    if not dry_run:
        upsert_experiment(exp, experiments_root)
    opp = _load_opportunity(exp["opportunity_id"], opportunities_root)
    return ExpOpResult(True, experiment=exp, opportunity=opp)
