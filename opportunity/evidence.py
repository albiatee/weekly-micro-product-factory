"""Opportunity Evidence model (Phase 3).

Separates FACT/evidence (traceable to Signals) from ASSUMPTIONS and UNKNOWNS.
Does not prove market demand. Does not start experiments.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

EVIDENCE_TYPES = frozenset(
    {
        "signal_excerpt",
        "signal_problem_statement",
        "signal_classification",
        "multi_signal_theme",
    }
)

ASSUMPTION_DEFAULTS = (
    {
        "assumption": "Target users would pay or switch for a better solution.",
        "importance": "high",
        "confidence": "low",
        "status": "untested",
    },
    {
        "assumption": "The problem occurs frequently enough to justify a product.",
        "importance": "high",
        "confidence": "low",
        "status": "untested",
    },
)

UNKNOWN_DEFAULTS = (
    "Market size is unknown.",
    "Willingness to pay is not evidenced beyond source signals.",
    "Problem frequency/severity distribution is unknown.",
    "Geographic demand is unverified unless geo_hint was present on signals.",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_evidence_items(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One evidence item per signal — always referenced by signal id."""
    items: list[dict[str, Any]] = []
    for s in signals:
        sid = str(s.get("id") or "")
        if not sid.startswith("sig_"):
            continue
        summary = (
            str(s.get("problem_statement") or "").strip()
            or str(s.get("raw_text") or "").strip()[:280]
        )
        items.append(
            {
                "type": "signal_excerpt",
                "signal_id": sid,
                "summary": summary,
                "captured_at": s.get("captured_at") or _now(),
                "strength": s.get("evidence_strength") or "weak",
                "intent_type": s.get("intent_type"),
                "source": s.get("source"),
                "url": s.get("url"),
                "relevance": "problem_description",
            }
        )
    if len(signals) > 1 and items:
        items.append(
            {
                "type": "multi_signal_theme",
                "signal_id": items[0]["signal_id"],
                "signal_ids": [i["signal_id"] for i in items if i.get("type") == "signal_excerpt"],
                "summary": f"Theme derived from {len(signals)} linked signals (not independent proof).",
                "captured_at": _now(),
                "strength": "weak",
                "relevance": "cross_signal_pattern",
            }
        )
    return items


def default_assumptions() -> list[dict[str, Any]]:
    return [dict(a) for a in ASSUMPTION_DEFAULTS]


def default_unknowns(signals: list[dict[str, Any]]) -> list[str]:
    unknowns = list(UNKNOWN_DEFAULTS)
    if not any(s.get("geo_hint") for s in signals):
        unknowns.append("Primary geography not stated on source signals.")
    return unknowns


def aggregate_opportunity_evidence_strength(evidence: list[dict[str, Any]]) -> str:
    """Deterministic roll-up. Strong Signal ≠ validated Opportunity."""
    if not evidence:
        return "none"
    ranks = {"strong": 3, "medium": 2, "weak": 1, "invalid": 0, "none": 0}
    scores = [ranks.get(str(e.get("strength") or "weak"), 1) for e in evidence if e.get("type") == "signal_excerpt"]
    if not scores:
        return "weak"
    best = max(scores)
    if best >= 3 and len(scores) >= 2:
        return "medium"  # multiple strong signals still only medium at opp level
    if best >= 3:
        return "medium"  # single strong signal → medium opportunity evidence
    if best >= 2:
        return "medium" if len(scores) >= 2 else "weak"
    return "weak"


def is_evidence_ready(opp: dict[str, Any]) -> tuple[bool, list[str]]:
    """Gate for advancing toward experiments. Not market validation."""
    errors: list[str] = []
    problem = str(opp.get("problem") or opp.get("problem_statement") or "").strip()
    if len(problem) < 20:
        errors.append("problem statement missing or too short")

    audience = str(opp.get("audience") or opp.get("target_user") or "").strip()
    if not audience:
        errors.append("target user / audience missing")

    sids = opp.get("signal_ids") or []
    if not isinstance(sids, list) or not sids:
        errors.append("source signal_ids required")
    else:
        for i, sid in enumerate(sids):
            if not isinstance(sid, str) or not sid.startswith("sig_"):
                errors.append(f"signal_ids[{i}] must be sig_...")

    evidence = opp.get("evidence")
    if not isinstance(evidence, list) or len(evidence) == 0:
        errors.append("evidence list required and non-empty")
    else:
        for i, ev in enumerate(evidence):
            if not isinstance(ev, dict):
                errors.append(f"evidence[{i}] must be object")
                continue
            if not str(ev.get("summary") or "").strip():
                errors.append(f"evidence[{i}].summary required")
            ref = ev.get("signal_id") or (ev.get("signal_ids") or [None])[0]
            if not ref or not str(ref).startswith("sig_"):
                errors.append(f"evidence[{i}] must reference signal_id")

    if "assumptions" not in opp or not isinstance(opp.get("assumptions"), list):
        errors.append("assumptions list required (may document untested claims)")
    if "unknowns" not in opp or not isinstance(opp.get("unknowns"), list):
        errors.append("unknowns list required")

    return len(errors) == 0, errors


def attach_evidence_layer(
    opp: dict[str, Any],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Enrich opportunity with evidence, assumptions, unknowns. Idempotent-ish."""
    out = dict(opp)
    if not out.get("evidence"):
        out["evidence"] = build_evidence_items(signals)
    if not out.get("assumptions"):
        out["assumptions"] = default_assumptions()
    if not out.get("unknowns"):
        out["unknowns"] = default_unknowns(signals)
    out["evidence_strength"] = aggregate_opportunity_evidence_strength(out["evidence"])
    # aliases for readability without breaking existing field names
    if not out.get("problem_statement"):
        out["problem_statement"] = out.get("problem")
    if not out.get("target_user"):
        out["target_user"] = out.get("audience")
    if not out.get("solution_direction"):
        out["solution_direction"] = out.get("solution_type")
    out["notes"] = (
        str(out.get("notes") or "")
        + " | Phase 3 evidence layer: evidence is signal-backed; assumptions untested; "
        "evidence_strength is not market validation."
    ).strip(" |")
    return out
