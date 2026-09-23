"""Deterministic metric formulas — only from present data; no invention."""
from __future__ import annotations

from typing import Any


def _rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(num / den, 4)


def compute_counts(
    opportunities: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    distribution_plans: dict[str, dict[str, Any]],
    distribution_actions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    opp_by_status: dict[str, int] = {}
    for o in opportunities.values():
        st = str(o.get("status") or "unknown")
        opp_by_status[st] = opp_by_status.get(st, 0) + 1

    exp_by_status: dict[str, int] = {}
    for e in experiments.values():
        st = str(e.get("status") or "unknown")
        exp_by_status[st] = exp_by_status.get(st, 0) + 1

    dec_by_verdict: dict[str, int] = {}
    for d in decisions.values():
        v = str(d.get("verdict") or "unknown")
        dec_by_verdict[v] = dec_by_verdict.get(v, 0) + 1

    plan_by_status: dict[str, int] = {}
    for p in distribution_plans.values():
        st = str(p.get("status") or "unknown")
        plan_by_status[st] = plan_by_status.get(st, 0) + 1

    n_opp = len(opportunities)
    n_exp = len(experiments)
    n_dec = len(decisions)
    n_plans = len(distribution_plans)
    n_actions = len(distribution_actions)

    completed_exp = exp_by_status.get("completed", 0)
    # started = running + completed + aborted (ever left planned)
    started_exp = (
        exp_by_status.get("running", 0)
        + completed_exp
        + exp_by_status.get("aborted", 0)
    )
    execute_n = dec_by_verdict.get("execute", 0)
    shipped_n = opp_by_status.get("shipped", 0)
    # opportunities that have a decision recorded
    opp_with_decision = sum(1 for o in opportunities.values() if o.get("latest_decision_id"))

    return {
        "opportunities_total": n_opp,
        "opportunities_by_status": dict(sorted(opp_by_status.items())),
        "experiments_total": n_exp,
        "experiments_by_status": dict(sorted(exp_by_status.items())),
        "decisions_total": n_dec,
        "decisions_by_verdict": dict(sorted(dec_by_verdict.items())),
        "shipped_opportunities": shipped_n,
        "distribution_plans_total": n_plans,
        "distribution_plans_by_status": dict(sorted(plan_by_status.items())),
        "distribution_actions_total": n_actions,
        "rates": {
            "execution_rate": _rate(execute_n, n_dec),
            "experiment_completion_rate": _rate(completed_exp, started_exp),
            "shipping_rate_among_decided": _rate(shipped_n, opp_with_decision),
        },
        "notes": {
            "execution_rate": "execute decisions / total decisions (None if no decisions)",
            "experiment_completion_rate": "completed / (running+completed+aborted)",
            "shipping_rate_among_decided": "shipped / opportunities with latest_decision_id",
            "missing_data": "Rates are null when denominator is zero; metrics never invented.",
        },
    }


def collect_operator_metrics(
    experiments: dict[str, dict[str, Any]],
    distribution_plans: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Surface operator-supplied metrics only; separate experiment vs distribution."""
    exp_results = []
    for eid, e in experiments.items():
        r = e.get("results")
        if isinstance(r, dict) and (r.get("metrics") or r.get("qualitative_notes")):
            exp_results.append(
                {
                    "source": "experiment",
                    "experiment_id": eid,
                    "opportunity_id": e.get("opportunity_id"),
                    "metrics": r.get("metrics"),
                    "qualitative_notes": r.get("qualitative_notes"),
                    "passed": r.get("passed"),
                }
            )
    dist_results = []
    for pid, p in distribution_plans.items():
        r = p.get("results")
        if isinstance(r, dict) and (r.get("metrics") or r.get("qualitative_notes")):
            dist_results.append(
                {
                    "source": "distribution",
                    "distribution_id": pid,
                    "opportunity_id": p.get("opportunity_id"),
                    "metrics": r.get("metrics"),
                    "qualitative_notes": r.get("qualitative_notes"),
                }
            )
    return {
        "experiment_results": exp_results,
        "distribution_results": dist_results,
        "disclaimer": (
            "These metrics are operator-recorded only. "
            "Votes/signups/clicks are not sales or proven demand."
        ),
    }
