"""Decision Gate pipeline — explicit human (or human+suggestion) verdicts only.

Phase 5: convert completed Experiment evidence into an auditable Decision.
Does NOT auto-derive verdict from metrics. Does NOT run production (Phase 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.validate import (
    validate_decision,
    validate_opportunity,
    validate_opportunity_transition,
)

from discovery.store import list_signals
from experiment.store import list_experiments
from opportunity.store import list_opportunities, upsert_opportunity

from .build import build_decision
from .store import list_decisions, upsert_decision

MIN_RATIONALE_LEN = 20


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class DecisionResult:
    ok: bool
    decision: dict[str, Any] | None = None
    opportunity: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


VERDICT_TO_STATUS = {
    "execute": "building",
    "iterate": "iterating",
    "kill": "killed",
}

ALLOWED_OPP_STATUSES = frozenset({"experimenting"})


def _validate_evidence(
    evidence_refs: list[str],
    *,
    opportunity_id: str,
    experiment_id: str | None,
    experiments: dict[str, dict[str, Any]],
    signals: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for ref in evidence_refs:
        if ref.startswith("exp_"):
            exp = experiments.get(ref)
            if not exp:
                errors.append(f"evidence exp not found: {ref}")
                continue
            if exp.get("opportunity_id") != opportunity_id:
                errors.append(
                    f"evidence {ref} belongs to opportunity {exp.get('opportunity_id')!r}, "
                    f"not {opportunity_id!r}"
                )
        elif ref.startswith("sig_"):
            if ref not in signals:
                errors.append(f"evidence sig not found: {ref}")
        else:
            errors.append(f"invalid evidence prefix: {ref}")

    if experiment_id:
        exp = experiments.get(experiment_id)
        if not exp:
            errors.append(f"experiment_id not found: {experiment_id}")
        elif exp.get("opportunity_id") != opportunity_id:
            errors.append(
                f"experiment_id {experiment_id} not linked to opportunity {opportunity_id}"
            )
        elif exp.get("status") != "completed":
            errors.append(
                f"experiment {experiment_id} status is {exp.get('status')!r}; "
                f"Decision requires completed experiment"
            )
        if experiment_id not in evidence_refs:
            errors.append("experiment_id must also appear in evidence_refs")

    return errors


def create_decision(
    *,
    opportunity_id: str,
    verdict: str,
    reason: str,
    evidence_refs: list[str],
    decided_by: str,
    experiment_id: str | None = None,
    next_action: str | None = None,
    agent_suggestion: str | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    signals_root: Path | None = None,
    decisions_root: Path | None = None,
    dry_run: bool = False,
) -> DecisionResult:
    """Create Decision and advance Opportunity: experimenting → decided → outcome.

    Requires a completed Experiment. Snapshots predefined criteria from that experiment.
    Does NOT auto-derive verdict from experiment.passed or scores.
    Does NOT trigger production builds (Phase 6).
    """
    opps = list_opportunities(opportunities_root)
    opp = opps.get(opportunity_id)
    if not opp:
        return DecisionResult(False, errors=[f"opportunity not found: {opportunity_id}"])

    if opp.get("status") not in ALLOWED_OPP_STATUSES:
        return DecisionResult(
            False,
            opportunity=opp,
            errors=[
                f"opportunity status {opp.get('status')!r} cannot receive Decision "
                f"(expected one of {sorted(ALLOWED_OPP_STATUSES)})"
            ],
        )

    if not (reason or "").strip() or len((reason or "").strip()) < MIN_RATIONALE_LEN:
        return DecisionResult(
            False,
            opportunity=opp,
            errors=[
                f"rationale/reason required (min {MIN_RATIONALE_LEN} chars); "
                "explain evidence vs predefined criteria"
            ],
        )

    if not experiment_id:
        return DecisionResult(
            False,
            opportunity=opp,
            errors=["experiment_id is required; Decision must evaluate a specific completed Experiment"],
        )

    experiments = list_experiments(experiments_root)
    signals = list_signals(signals_root)
    decisions = list_decisions(decisions_root)

    # One finalized Decision per Experiment
    for existing in decisions.values():
        if existing.get("experiment_id") == experiment_id:
            return DecisionResult(
                False,
                opportunity=opp,
                errors=[
                    f"experiment {experiment_id} already has decision {existing.get('id')}; "
                    "refusing overwrite — run a new experiment for a new evidence cycle"
                ],
            )

    if opp.get("latest_decision_id"):
        return DecisionResult(
            False,
            opportunity=opp,
            errors=[
                f"opportunity already has latest_decision_id={opp['latest_decision_id']!r}; "
                f"refusing silent overwrite"
            ],
        )

    refs = list(evidence_refs or [])
    if experiment_id not in refs:
        refs.append(experiment_id)

    evid_errors = _validate_evidence(
        refs,
        opportunity_id=opportunity_id,
        experiment_id=experiment_id,
        experiments=experiments,
        signals=signals,
    )
    if evid_errors:
        return DecisionResult(False, opportunity=opp, errors=evid_errors)

    exp = experiments[experiment_id]
    if exp.get("status") != "completed":
        return DecisionResult(
            False,
            opportunity=opp,
            errors=[
                f"Decision requires completed Experiment; got status={exp.get('status')!r}"
            ],
        )
    if not exp.get("results") and not exp.get("observations"):
        return DecisionResult(
            False,
            opportunity=opp,
            errors=["completed experiment has no results/observations to evaluate"],
        )

    # Predefined criteria must still be present (immutability from Phase 4)
    if not exp.get("measurement_plan"):
        return DecisionResult(
            False,
            opportunity=opp,
            errors=["experiment missing measurement_plan in criteria snapshot source"],
        )
    has_success = exp.get("success_criteria") is not None or exp.get("success_threshold") is not None
    has_failure = exp.get("failure_criteria") is not None
    if not has_success or not has_failure:
        return DecisionResult(
            False,
            opportunity=opp,
            errors=[
                "experiment missing success_criteria and/or failure_criteria; "
                "cannot decide without predefined criteria"
            ],
        )

    try:
        dec = build_decision(
            opportunity_id=opportunity_id,
            verdict=verdict,
            reason=reason,
            evidence_refs=refs,
            decided_by=decided_by,
            experiment_id=experiment_id,
            experiment=exp,
            next_action=next_action,
            agent_suggestion=agent_suggestion,
        )
    except ValueError as e:
        return DecisionResult(False, opportunity=opp, errors=[str(e)])

    vr = validate_decision(dec)
    if not vr.ok:
        return DecisionResult(False, decision=dec, opportunity=opp, errors=vr.errors)

    tr1 = validate_opportunity_transition(opp["status"], "decided")
    if not tr1.ok:
        return DecisionResult(False, decision=dec, opportunity=opp, errors=tr1.errors)

    outcome = VERDICT_TO_STATUS.get(verdict)
    if not outcome:
        return DecisionResult(
            False, decision=dec, opportunity=opp, errors=[f"unknown verdict: {verdict}"]
        )

    tr2 = validate_opportunity_transition("decided", outcome)
    if not tr2.ok:
        return DecisionResult(False, decision=dec, opportunity=opp, errors=tr2.errors)

    opp_updated = {
        **opp,
        "status": outcome,
        "latest_decision_id": dec["id"],
        "updated_at": _now(),
    }

    vr_opp = validate_opportunity(opp_updated)
    if not vr_opp.ok:
        return DecisionResult(
            False, decision=dec, opportunity=opp_updated, errors=vr_opp.errors
        )

    if not dry_run:
        upsert_decision(dec, decisions_root)
        upsert_opportunity(opp_updated, opportunities_root)

    return DecisionResult(True, decision=dec, opportunity=opp_updated)
