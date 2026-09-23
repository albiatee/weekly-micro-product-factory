"""Deterministic Signal → Opportunity candidate generation."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .score import score_opportunity


def generate_opportunity_id() -> str:
    return f"opp_{uuid.uuid4().hex[:16]}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _title_from_text(text: str, max_len: int = 80) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return "Untitled opportunity candidate"
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def infer_solution_type(text: str) -> str:
    """Heuristic mapping only — hypothesis, not validation."""
    t = (text or "").lower()
    if re.search(r"\b(marketplace|two.?sided|buyers and sellers|سوق وسيط)\b", t):
        return "marketplace"
    if re.search(r"\b(saas|subscription|dashboard|multi.?tenant)\b", t):
        return "saas"
    if re.search(r"\b(ship|physical|hardware|print|منتج مادي)\b", t):
        return "physical_hybrid"
    if re.search(r"\b(service|done for you|concierge|consult|خدمة)\b", t):
        return "concierge"
    if re.search(r"\b(template|pack|ebook|course|محتوى|قالب)\b", t):
        return "content_pack"
    if re.search(r"\b(tool|app|page|offline|html|calculator|tracker|أداة|صفحة)\b", t):
        return "digital_micro"
    return "unknown"


def infer_geo(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Only use geo_hint/language present on signals; otherwise honest unknown."""
    hints = [str(s.get("geo_hint")).strip() for s in signals if s.get("geo_hint")]
    langs = []
    for s in signals:
        if s.get("language"):
            lang = str(s["language"]).strip()
            if lang and lang not in langs:
                langs.append(lang)

    if not hints and not langs:
        return {
            "primary": "unknown",
            "region": "unknown",
            "languages": [],
            "rationale": "No geo_hint or language on source signals; geography unverified.",
        }

    primary = hints[0] if hints else "unknown"
    # crude region bucket
    region = "unknown"
    p = primary.lower()
    if p in ("global", "worldwide"):
        region = "GLOBAL"
    elif p.upper() in ("SA", "AE", "EG", "JO", "MA", "TN") or "mena" in p:
        region = "MENA"
    elif p.upper() in ("US", "CA") or p in ("usa", "america"):
        region = "NA"
    elif p.upper() in ("UK", "DE", "FR", "EU"):
        region = "EU"

    rationale_parts = []
    if hints:
        rationale_parts.append(f"geo_hint from signals: {', '.join(hints[:3])}")
    if langs:
        rationale_parts.append(f"languages on signals: {', '.join(langs)}")
    rationale_parts.append("Not proof of geographic demand.")

    return {
        "primary": primary,
        "region": region,
        "languages": langs,
        "rationale": " ".join(rationale_parts),
    }


def build_opportunity_from_signals(
    signals: list[dict[str, Any]],
    *,
    created_by: str = "system:opportunity_engine",
    opportunity_id: str | None = None,
) -> dict[str, Any]:
    """Build a hypothesized Opportunity from one or more existing Signals.

    Distinguishes signal-derived text from generated hypotheses in field content.
    Does not invent market size, revenue, or validated demand.
    """
    if not signals:
        raise ValueError("at least one signal is required")

    signal_ids = [str(s["id"]) for s in signals]
    combined = "\n".join(str(s.get("raw_text") or "") for s in signals)
    primary_text = str(signals[0].get("raw_text") or "").strip()

    title = _title_from_text(primary_text)
    problem = primary_text if len(signals) == 1 else (
        f"Recurring theme across {len(signals)} signals: " + _title_from_text(combined, 200)
    )

    # Audience: only if explicit markers; else honest unknown
    aud_match = re.search(
        r"\b(?:for|لل)\s+([A-Za-z\u0600-\u06FF][A-Za-z0-9\u0600-\u06FF \-]{2,40})",
        primary_text,
        re.I,
    )
    if aud_match:
        audience = aud_match.group(1).strip()
    else:
        audience = "unspecified (not stated in source signals)"

    solution_type = infer_solution_type(combined)
    geo = infer_geo(signals)
    score = score_opportunity(signals=signals, solution_type=solution_type, problem=problem)

    value_proposition = (
        f"[HYPOTHESIS] A {solution_type} approach may address: {title}. "
        f"Not validated by market evidence beyond the linked signals."
    )
    hypothesis = (
        f"[HYPOTHESIS] If we offer a {solution_type} solution for the stated problem, "
        f"relevant users may show interest. This is a testable claim, not proven demand."
    )

    now = _now()
    opp: dict[str, Any] = {
        "id": opportunity_id or generate_opportunity_id(),
        "status": "hypothesized",
        "title": title,
        "problem": problem,
        "audience": audience,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "signal_ids": signal_ids,
        "value_proposition": value_proposition,
        "hypothesis": hypothesis,
        "solution_type": solution_type,
        "geo": geo,
        "score": score,
        "notes": (
            "Phase 3 generated candidate. Scores are prioritization heuristics only. "
            "Do not treat as market validation."
        ),
    }
    return opp
