"""Deterministic metric formulas — only from present data; no invention.

Counting semantics: **records** in each store (not unique cross-store entities
unless a metric name says unique_*).
Missing stores → metrics omitted or marked unavailable, not fabricated facts.
"""
from __future__ import annotations

from typing import Any

from opportunity.evidence import is_evidence_ready


def _rate(num: int, den: int) -> float | None:
    if den <= 0:
        return None
    return round(num / den, 4)


def compute_signal_counts(signals: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    if signals is None:
        return {"available": False, "note": "signals store not provided"}
    by_q: dict[str, int] = {}
    by_intent: dict[str, int] = {}
    for s in signals.values():
        q = str(s.get("qualification_status") or "unknown")
        by_q[q] = by_q.get(q, 0) + 1
        intent = str(s.get("intent_type") or "unknown")
        by_intent[intent] = by_intent.get(intent, 0) + 1
    return {
        "available": True,
        "signals_total": len(signals),
        "signals_by_qualification": dict(sorted(by_q.items())),
        "signals_by_intent": dict(sorted(by_intent.items())),
        "qualified": by_q.get("qualified", 0),
        "review": by_q.get("review", 0),
        "rejected": by_q.get("rejected", 0),
    }


def compute_production_counts(specs: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    if specs is None:
        return {"available": False, "note": "production store not provided"}
    by_st: dict[str, int] = {}
    for s in specs.values():
        st = str(s.get("production_status") or "unknown")
        by_st[st] = by_st.get(st, 0) + 1
    return {
        "available": True,
        "production_specs_total": len(specs),
        "production_specs_by_status": dict(sorted(by_st.items())),
    }


def compute_counts(
    opportunities: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    distribution_plans: dict[str, dict[str, Any]],
    distribution_actions: dict[str, dict[str, Any]],
    signals: dict[str, dict[str, Any]] | None = None,
    production_specs: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    opp_by_status: dict[str, int] = {}
    evidence_ready_n = 0
    for o in opportunities.values():
        st = str(o.get("status") or "unknown")
        opp_by_status[st] = opp_by_status.get(st, 0) + 1
        ready, _ = is_evidence_ready(o)
        if ready:
            evidence_ready_n += 1

    exp_by_status: dict[str, int] = {}
    for e in experiments.values():
        st = str(e.get("status") or "unknown")
        exp_by_status[st] = exp_by_status.get(st, 0) + 1

    dec_by_verdict: dict[str, int] = {}
    for d in decisions.values():
        v = str(d.get("verdict") or d.get("decision") or "unknown")
        dec_by_verdict[v] = dec_by_verdict.get(v, 0) + 1

    plan_by_status: dict[str, int] = {}
    pub_success = 0
    pub_failed = 0
    pub_not_recorded = 0
    for p in distribution_plans.values():
        st = str(p.get("status") or "unknown")
        plan_by_status[st] = plan_by_status.get(st, 0) + 1
        pub = p.get("publication")
        if isinstance(pub, dict) and "success" in pub:
            if pub.get("success") is True:
                pub_success += 1
            elif pub.get("success") is False:
                pub_failed += 1
            else:
                pub_not_recorded += 1
        elif st in ("published", "completed"):
            # legacy completed without publication object
            pub_success += 1
        elif st == "failed":
            pub_failed += 1
        elif st in ("planned", "prepared", "ready", "running", "paused"):
            pub_not_recorded += 1

    n_opp = len(opportunities)
    n_exp = len(experiments)
    n_dec = len(decisions)
    n_plans = len(distribution_plans)
    n_actions = len(distribution_actions)

    completed_exp = exp_by_status.get("completed", 0)
    started_exp = (
        exp_by_status.get("running", 0)
        + completed_exp
        + exp_by_status.get("aborted", 0)
    )
    execute_n = dec_by_verdict.get("execute", 0)
    shipped_n = opp_by_status.get("shipped", 0)
    opp_with_decision = sum(1 for o in opportunities.values() if o.get("latest_decision_id"))

    out: dict[str, Any] = {
        "counting_semantics": "record_counts",
        "opportunities_total": n_opp,
        "opportunities_by_status": dict(sorted(opp_by_status.items())),
        "opportunities_evidence_ready": evidence_ready_n,
        "experiments_total": n_exp,
        "experiments_by_status": dict(sorted(exp_by_status.items())),
        "experiments_completed": completed_exp,
        "decisions_total": n_dec,
        "decisions_by_verdict": dict(sorted(dec_by_verdict.items())),
        "decisions_execute": execute_n,
        "decisions_iterate": dec_by_verdict.get("iterate", 0),
        "decisions_kill": dec_by_verdict.get("kill", 0),
        "shipped_opportunities": shipped_n,
        "distribution_plans_total": n_plans,
        "distribution_plans_by_status": dict(sorted(plan_by_status.items())),
        "distribution_planned": plan_by_status.get("planned", 0),
        "distribution_prepared": plan_by_status.get("prepared", 0)
        + plan_by_status.get("ready", 0),
        "distribution_publication_success": pub_success,
        "distribution_publication_failed": pub_failed,
        "distribution_publication_not_recorded": pub_not_recorded,
        "distribution_actions_total": n_actions,
        "rates": {
            "experiment_completion_rate": _rate(completed_exp, started_exp),
            "decision_rate_among_opportunities": _rate(opp_with_decision, n_opp),
            "execute_rate_among_decisions": _rate(execute_n, n_dec),
            "execution_rate": _rate(execute_n, n_dec),  # legacy alias
            "ship_rate_among_execute": _rate(shipped_n, execute_n),
            "shipping_rate_among_decided": _rate(shipped_n, opp_with_decision),  # legacy
        },
        "notes": [
            "Rates are None when denominator is zero (not zero).",
            "Does not invent market demand or conversion from missing data.",
        ],
    }
    out["signals"] = compute_signal_counts(signals)
    out["production"] = compute_production_counts(production_specs)
    return out


def compute_funnel(
    signals: dict[str, dict[str, Any]] | None,
    opportunities: dict[str, dict[str, Any]],
    experiments: dict[str, dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    production_specs: dict[str, dict[str, Any]] | None,
    distribution_plans: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Lifecycle funnel as sequential **record counts** (not forced equality)."""
    sig = compute_signal_counts(signals)
    prod = compute_production_counts(production_specs)

    stages = [
        {
            "stage": "signals",
            "count": sig.get("signals_total") if sig.get("available") else None,
            "available": sig.get("available"),
        },
        {
            "stage": "qualified_signals",
            "count": sig.get("qualified") if sig.get("available") else None,
            "available": sig.get("available"),
        },
        {
            "stage": "opportunities",
            "count": len(opportunities),
            "available": True,
        },
        {
            "stage": "evidence_ready_opportunities",
            "count": sum(1 for o in opportunities.values() if is_evidence_ready(o)[0]),
            "available": True,
        },
        {
            "stage": "experiments",
            "count": len(experiments),
            "available": True,
        },
        {
            "stage": "experiments_completed",
            "count": sum(1 for e in experiments.values() if e.get("status") == "completed"),
            "available": True,
        },
        {
            "stage": "decisions",
            "count": len(decisions),
            "available": True,
        },
        {
            "stage": "decisions_execute",
            "count": sum(
                1
                for d in decisions.values()
                if (d.get("verdict") or d.get("decision")) == "execute"
            ),
            "available": True,
        },
        {
            "stage": "production_specs",
            "count": prod.get("production_specs_total") if prod.get("available") else None,
            "available": prod.get("available"),
        },
        {
            "stage": "distribution_plans",
            "count": len(distribution_plans),
            "available": True,
        },
        {
            "stage": "distribution_publication_recorded_success",
            "count": sum(
                1
                for p in distribution_plans.values()
                if (isinstance(p.get("publication"), dict) and p["publication"].get("success") is True)
                or p.get("status") in ("published", "completed")
            ),
            "available": True,
        },
    ]
    return {
        "semantics": "record_counts_per_stage_not_forced_join",
        "stages": stages,
        "note": "Stages are independent counts; drop-off is not always causal.",
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
