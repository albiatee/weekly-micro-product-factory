"""Deterministic opportunity selection — no LLM authority."""
from __future__ import annotations

from typing import Any

from opportunity.evidence import is_evidence_ready


_STRENGTH = {"strong": 3, "medium": 2, "weak": 1, "none": 0, "invalid": 0}


def _strength_rank(opp: dict[str, Any]) -> int:
    evidence = opp.get("evidence") or []
    best = 0
    for e in evidence:
        if not isinstance(e, dict):
            continue
        best = max(best, _STRENGTH.get(str(e.get("strength") or "weak"), 1))
    return best


def is_eligible(
    opp: dict[str, Any],
    *,
    config: dict[str, Any],
    active_experiment_ids: set[str] | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ready, errs = is_evidence_ready(opp)
    if not ready:
        reasons.extend(errs or ["not evidence_ready"])
    sids = opp.get("signal_ids") or []
    min_q = int(config.get("minimum_qualified_source_count", 1))
    if len(sids) < min_q:
        reasons.append(f"qualified_source_count {len(sids)} < {min_q}")
    active = opp.get("active_experiment_id")
    if active:
        reasons.append(f"active_experiment:{active}")
    if active_experiment_ids and active in active_experiment_ids:
        reasons.append("experiment_in_active_set")
    status = str(opp.get("status") or "")
    if status in ("killed", "building", "completed"):
        reasons.append(f"status_blocked:{status}")
    return (len(reasons) == 0, reasons)


def score_opportunity(opp: dict[str, Any]) -> int:
    ready, _ = is_evidence_ready(opp)
    sids = opp.get("signal_ids") or []
    return (
        (100 if ready else 0)
        + 10 * _strength_rank(opp)
        + 1 * len(sids)
    )


def rank_opportunities(
    opportunities: list[dict[str, Any]],
    *,
    config: dict[str, Any],
) -> list[tuple[dict[str, Any], int]]:
    scored: list[tuple[dict[str, Any], int]] = []
    for opp in opportunities:
        ok, _ = is_eligible(opp, config=config)
        if not ok:
            continue
        scored.append((opp, score_opportunity(opp)))
    scored.sort(key=lambda t: (-t[1], str(t[0].get("id") or "")))
    return scored


def select_opportunities(
    opportunities: list[dict[str, Any]],
    *,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = int(config.get("max_opportunities_per_cycle", 1))
    ranked = rank_opportunities(opportunities, config=config)
    return [opp for opp, _ in ranked[: max(0, limit)]]
