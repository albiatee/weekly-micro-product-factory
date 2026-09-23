"""Deterministic prioritization heuristics (NOT market validation)."""
from __future__ import annotations

import re
from typing import Any


def _clamp(n: float) -> int:
    return int(max(0, min(100, round(n))))


def score_opportunity(
    *,
    signals: list[dict[str, Any]],
    solution_type: str,
    problem: str,
) -> dict[str, int]:
    """Return score object with dimensions 0–100.

    These are prioritization heuristics only — they do not prove demand,
    willingness to pay, or market size.
    """
    n = max(1, len(signals))
    text = " ".join(str(s.get("raw_text") or "") for s in signals).lower()
    problem_l = (problem or "").lower()

    # intensity: more corroborating signals + substance in text
    intensity = 25 + min(40, (n - 1) * 15) + min(20, len(problem) // 20)

    # willingness_to_pay: only bump if explicit pay language in signals (still not proof)
    pay_hits = len(re.findall(r"\b(pay|price|pricing|subscribe|subscription|buy|cost|\$|سعر|يدفع|اشتراك)\b", text))
    willingness = 15 + min(35, pay_hits * 12)

    # reachability: known language/geo hints slightly higher
    langs = [s.get("language") for s in signals if s.get("language")]
    geos = [s.get("geo_hint") for s in signals if s.get("geo_hint")]
    reachability = 25
    if langs:
        reachability += 20
    if geos:
        reachability += 15

    # competition_gap: unknown by default (conservative)
    competition_gap = 25
    if re.search(r"\b(no tool|missing|alternative|competitor|بديل|لا يوجد)\b", text):
        competition_gap = 45

    # feasibility by hypothesized solution type (not validation)
    feas_map = {
        "digital_micro": 70,
        "content_pack": 65,
        "concierge": 55,
        "saas": 40,
        "physical_hybrid": 35,
        "marketplace": 30,
        "unknown": 40,
    }
    feasibility = feas_map.get(solution_type, 40)

    # ethics: high unless sensitive patterns
    ethics = 85
    if re.search(r"\b(weapon|gambling|addiction|surveillance|سلاح|قمار)\b", text + " " + problem_l):
        ethics = 20

    dims = {
        "intensity": _clamp(intensity),
        "willingness_to_pay": _clamp(willingness),
        "reachability": _clamp(reachability),
        "competition_gap": _clamp(competition_gap),
        "feasibility": _clamp(feasibility),
        "ethics": _clamp(ethics),
    }
    # equal-ish weights; total is heuristic priority rank
    total = _clamp(sum(dims.values()) / len(dims))
    dims["total"] = total
    return dims
