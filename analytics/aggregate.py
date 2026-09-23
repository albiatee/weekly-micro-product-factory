"""Aggregate snapshot from store roots."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from decision.store import list_decisions
from discovery.store import list_signals
from distribution.store import list_actions, list_plans
from experiment.store import list_experiments
from opportunity.store import list_opportunities

from .metrics import collect_operator_metrics, compute_counts


def build_snapshot(
    *,
    opportunities_root: Path | None = None,
    experiments_root: Path | None = None,
    decisions_root: Path | None = None,
    signals_root: Path | None = None,
    distribution_root: Path | None = None,
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    opportunities = list_opportunities(opportunities_root)
    experiments = list_experiments(experiments_root)
    decisions = list_decisions(decisions_root)
    signals = list_signals(signals_root)
    plans = list_plans(distribution_root)
    actions = list_actions(distribution_root)

    if opportunity_id:
        opportunities = {k: v for k, v in opportunities.items() if k == opportunity_id}
        experiments = {
            k: v for k, v in experiments.items() if v.get("opportunity_id") == opportunity_id
        }
        decisions = {
            k: v for k, v in decisions.items() if v.get("opportunity_id") == opportunity_id
        }
        plans = {
            k: v for k, v in plans.items() if v.get("opportunity_id") == opportunity_id
        }
        plan_ids = set(plans)
        actions = {
            k: v for k, v in actions.items() if v.get("distribution_id") in plan_ids
        }
        # signals referenced by filtered opportunities
        sids: set[str] = set()
        for o in opportunities.values():
            for sid in o.get("signal_ids") or []:
                sids.add(sid)
        signals = {k: v for k, v in signals.items() if k in sids}

    counts = compute_counts(opportunities, experiments, decisions, plans, actions)
    operator = collect_operator_metrics(experiments, plans)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filter": {"opportunity_id": opportunity_id},
        "counts": counts,
        "operator_recorded": operator,
        "entity_totals": {
            "signals": len(signals),
            "opportunities": len(opportunities),
            "experiments": len(experiments),
            "decisions": len(decisions),
            "distribution_plans": len(plans),
            "distribution_actions": len(actions),
        },
    }
