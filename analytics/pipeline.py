"""Analytics + Learning pipeline — read-only on prior phases; optional persist."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from decision.store import list_decisions
from distribution.store import list_plans
from experiment.store import list_experiments
from opportunity.store import list_opportunities

from .aggregate import build_snapshot
from .learning import build_learning_for_opportunity
from .store import append_snapshot, list_learnings, upsert_learning


@dataclass
class AnalyticsResult:
    ok: bool
    snapshot: dict[str, Any] | None = None
    learnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_analytics(
    *,
    opportunity_id: str | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    decisions_root: Path | None = None,
    signals_root: Path | None = None,
    distribution_root: Path | None = None,
    analytics_root: Path | None = None,
    dry_run: bool = False,
) -> AnalyticsResult:
    snapshot = build_snapshot(
        opportunities_root=opportunities_root,
        experiments_root=experiments_root,
        decisions_root=decisions_root,
        signals_root=signals_root,
        distribution_root=distribution_root,
        opportunity_id=opportunity_id,
    )
    if not dry_run:
        append_snapshot(snapshot, analytics_root)
    return AnalyticsResult(ok=True, snapshot=snapshot)


def generate_learning_records(
    *,
    opportunity_id: str | None = None,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    decisions_root: Path | None = None,
    distribution_root: Path | None = None,
    analytics_root: Path | None = None,
    dry_run: bool = False,
) -> AnalyticsResult:
    opportunities = list_opportunities(opportunities_root)
    if opportunity_id:
        opportunities = {k: v for k, v in opportunities.items() if k == opportunity_id}
    experiments = list_experiments(experiments_root)
    decisions = list_decisions(decisions_root)
    plans = list_plans(distribution_root)

    learnings: list[dict[str, Any]] = []
    errors: list[str] = []
    for oid, opp in opportunities.items():
        lr = build_learning_for_opportunity(
            opp,
            experiments=experiments,
            decisions=decisions,
            distribution_plans=plans,
        )
        if lr is None:
            errors.append(f"skipped {oid}: insufficient evidence for LearningRecord")
            continue
        # Validate refs exist
        if lr.get("experiment_id") and lr["experiment_id"] not in experiments:
            errors.append(f"invalid experiment_id on learning for {oid}")
            continue
        if lr.get("decision_id") and lr["decision_id"] not in decisions:
            errors.append(f"invalid decision_id on learning for {oid}")
            continue
        learnings.append(lr)
        if not dry_run:
            upsert_learning(lr, analytics_root)

    return AnalyticsResult(ok=True, learnings=learnings, errors=errors)
