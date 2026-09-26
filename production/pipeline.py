"""Production Specification pipeline (Phase 6).

Creates auditable specs from execute Decisions. Does not deploy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from decision.store import list_decisions
from experiment.store import list_experiments
from opportunity.store import list_opportunities

from .spec import build_production_spec, is_production_ready
from .store import list_production_specs, upsert_production_spec


@dataclass
class SpecResult:
    ok: bool
    production_spec: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def create_production_spec(
    *,
    decision_id: str | None = None,
    opportunity_id: str | None = None,
    opportunities_root: Path | None = None,
    decisions_root: Path | None = None,
    experiments_root: Path | None = None,
    production_root: Path | None = None,
    dry_run: bool = False,
) -> SpecResult:
    """Create Production Spec from an execute Decision.

    Provide decision_id and/or opportunity_id (uses opportunity.latest_decision_id).
    """
    decisions = list_decisions(decisions_root)
    opportunities = list_opportunities(opportunities_root)
    experiments = list_experiments(experiments_root)
    specs = list_production_specs(production_root)

    dec = decisions.get(decision_id) if decision_id else None
    opp = opportunities.get(opportunity_id) if opportunity_id else None

    if dec is None and opp is not None:
        lid = opp.get("latest_decision_id")
        if lid:
            dec = decisions.get(lid)
            decision_id = lid
    if opp is None and dec is not None:
        opp = opportunities.get(dec.get("opportunity_id"))

    if not decision_id and not dec:
        return SpecResult(False, errors=["decision_id required or opportunity with latest_decision_id"])
    if not dec:
        return SpecResult(False, errors=[f"decision not found: {decision_id}"])
    if not opp:
        return SpecResult(False, errors=[f"opportunity not found for decision {dec.get('id')}"])

    # One active spec per decision
    for existing in specs.values():
        if existing.get("decision_id") == dec["id"]:
            return SpecResult(
                False,
                production_spec=existing,
                errors=[
                    f"decision {dec['id']} already has production spec {existing.get('id')}; "
                    "refusing duplicate"
                ],
            )

    exp = None
    eid = dec.get("experiment_id")
    if eid:
        exp = experiments.get(eid)
        if not exp:
            return SpecResult(False, errors=[f"experiment not found: {eid}"])

    ready, errs = is_production_ready(dec, opp, exp)
    if not ready:
        return SpecResult(False, errors=errs)

    spec = build_production_spec(decision=dec, opportunity=opp, experiment=exp)
    if not dry_run:
        upsert_production_spec(spec, production_root)
    return SpecResult(True, production_spec=spec)
