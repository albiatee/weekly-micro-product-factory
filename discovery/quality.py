"""Deterministic Signal Quality Layer (Phase 2).

Classification + evidence strength + qualification.
Does NOT invent market demand. Does NOT use LLM.
Does NOT change Opportunity lifecycle.
"""
from __future__ import annotations

import re
from typing import Any

from contracts.constants import DEMAND_SIDE_INTENTS

# --- pattern libraries (lowercase matching) ---

_SUPPLY = (
    r"\blooking for freelance\b",
    r"\blooking for (freelance|contract) (or contract )?work\b",
    r"\bfor hire\b",
    r"\bopen for (client )?work\b",
    r"\bavailable for (hire|work|projects)\b",
    r"\bdm me (on|if)\b",
    r"\bmy (rate|rates) (is|are)\b",
    r"\b\d+\s*usd/(week|hour|mo)\b",
    r"\bfreelance (writer|developer|dev|designer).{0,40}(open|available|looking)\b",
)

_PROMO = (
    r"\bcheck out my\b",
    r"\blaunching (our|my)\b",
    r"\bwe (just )?(built|launched|shipped)\b",
    r"\bi (just )?(built|launched|shipped)\b",
    r"\bintroducing\b.{0,30}\b(app|tool|saas|product)\b",
    r"\bproduct hunt\b",
    r"\bshow hn:\s*.{0,80}(app|tool|saas|platform)\b",
)

_NEWS = (
    r"\bpodcast episode\b",
    r"\b\d+th episode\b",
    r"\byoutube:\s*https?://\b",
    r"\bspotify\b",
    r"\bnewsletter\b",
)

_BUYING = (
    r"\bwilling to pay\b",
    r"\blooking to buy\b",
    r"\bready to pay\b",
    r"\bwould pay for\b",
    r"\bsubscription (is )?(too )?(expensive|costly)\b",
    r"\bcheaper alternative\b",
    r"\brecommend a (paid )?tool\b",
)

_WORKAROUND = (
    r"\bmanually\b",
    r"\bby hand\b",
    r"\bspreadsheet\b",
    r"\bexcel\b",
    r"\bgoogle sheets\b",
    r"\bcopy[- ]paste\b",
    r"\bworkaround\b",
    r"\binstead of\b",
)

_PROBLEM = (
    r"\bwaste(s|d|ing)?\b.{0,40}\b(time|hours|money|compute)\b",
    r"\bstruggl(e|es|ing)\b",
    r"\bcan'?t\b",
    r"\bcannot\b",
    r"\bunable to\b",
    r"\bbroken\b",
    r"\bfails? every\b",
    r"\bpain(ful)?\b",
    r"\bfrustrating\b",
    r"\btoo expensive\b",
    r"\bno (good )?way to\b",
    r"\bproblem (is|with)\b",
    r"\bi (keep|always) (having|getting)\b",
)

_REQUEST = (
    r"\bis there (a|any) (tool|app|way|service)\b",
    r"\bneed (a|an) (tool|way|app|solution)\b",
    r"\blooking for (a|an) (tool|app|solution|way)\b",
    r"\banyone know (a|of)\b",
    r"\bhow (can|do) i (automate|solve|fix)\b",
)

_QUESTION = (
    r"^ask hn:",
    r"\bhow do (you|i|people)\b",
    r"\bwhat (do|does|is) (everyone|people|you)\b",
    r"\bhas anyone\b",
)

_COMPLAINT = (
    r"\bhate (that|when|how)\b",
    r"\bsick of\b",
    r"\balways fails\b",
    r"\bunacceptable\b",
)

_FEATURE = (
    r"\bfeature request\b",
    r"\bplease add\b",
    r"\bwould be nice if\b",
    r"\bmissing (feature|option)\b",
    r"\bwhy (isn'?t|is there no)\b",
)

_NOISE = (
    r"^ask hn:\s*what is the most interesting project",
    r"^ask hn:\s*who is hiring",
    r"\bwhat are you working on\b",
)

_HN_BOILER = re.compile(
    r"(Article URL:|Comments URL:|Points:\s*\d+|# Comments:\s*\d+)",
    re.I,
)


def _any(patterns: tuple[str, ...], text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def clean_text_for_analysis(raw: str) -> str:
    t = (raw or "").strip()
    t = _HN_BOILER.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def classify_intent(raw_text: str, *, meta: dict[str, Any] | None = None) -> tuple[str, float]:
    """Return (intent_type, confidence 0..1). Deterministic priority order."""
    text = clean_text_for_analysis(raw_text).lower()
    if len(text) < 15:
        return "noise", 0.9

    if _any(_SUPPLY, text):
        return "supply", 0.92
    if _any(_PROMO, text):
        return "promotion", 0.85
    if _any(_NEWS, text) and not _any(_PROBLEM, text):
        return "news", 0.8
    if _any(_NOISE, text):
        return "noise", 0.85
    if _any(_BUYING, text):
        return "buying_intent", 0.8
    if _any(_WORKAROUND, text) and (_any(_PROBLEM, text) or _any(_REQUEST, text)):
        return "workaround", 0.75
    if _any(_COMPLAINT, text):
        return "complaint", 0.7
    if _any(_FEATURE, text):
        return "feature_request", 0.7
    if _any(_REQUEST, text):
        return "request", 0.72
    if _any(_PROBLEM, text):
        return "problem", 0.75
    if _any(_QUESTION, text):
        return "question", 0.65
    if _any(_WORKAROUND, text):
        return "workaround", 0.6

    # Short HN-style title only → weak unknown/noise
    if len(text) < 80 and not re.search(r"[.!?]", text):
        return "noise", 0.55
    return "unknown", 0.4


def assess_evidence_strength(intent: str, raw_text: str) -> str:
    text = clean_text_for_analysis(raw_text).lower()
    if intent in ("supply", "promotion", "news", "noise"):
        return "invalid"
    if intent == "unknown":
        return "weak"

    has_specific = bool(
        re.search(
            r"\b(every (day|week|month)|hours?|minutes?|manually|ci/?cd|invoice|siri|macos|pipeline)\b",
            text,
            re.I,
        )
    )
    has_behavior = _any(_WORKAROUND, text) or _any(_BUYING, text)
    has_pain = _any(_PROBLEM, text) or _any(_COMPLAINT, text)

    if intent in ("buying_intent",) and (has_pain or has_specific):
        return "strong"
    if intent in ("problem", "workaround", "complaint", "request") and has_specific and has_behavior:
        return "strong"
    if intent in ("problem", "workaround", "complaint", "request", "feature_request") and (
        has_pain or has_specific
    ):
        return "medium"
    if intent in ("problem", "request", "complaint", "workaround", "feature_request", "buying_intent"):
        return "medium" if len(text) > 120 else "weak"
    if intent == "question":
        return "medium" if has_pain or has_specific else "weak"
    return "weak"


def qualify(intent: str, strength: str) -> str:
    """qualified | review | rejected — policy for opportunity eligibility."""
    if strength == "invalid" or intent in ("supply", "promotion", "news", "noise"):
        return "rejected"
    if intent == "unknown":
        return "review" if strength != "invalid" else "rejected"
    if intent in DEMAND_SIDE_INTENTS:
        if strength == "strong":
            return "qualified"
        if strength == "medium":
            return "qualified" if intent in ("problem", "buying_intent", "workaround", "request", "complaint") else "review"
        if strength == "weak":
            return "review"
    return "review"


def extract_problem_statement(raw_text: str, intent: str) -> str | None:
    cleaned = clean_text_for_analysis(raw_text)
    if intent in ("supply", "promotion", "news", "noise"):
        return None
    # First meaningful sentence / first 280 chars
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    for p in parts:
        p = p.strip()
        if len(p) >= 20:
            return p[:400]
    return cleaned[:400] if len(cleaned) >= 20 else None


def apply_quality(signal: dict[str, Any]) -> dict[str, Any]:
    """Enrich signal dict with quality fields. Idempotent if already set and valid."""
    out = dict(signal)
    raw = str(out.get("raw_text") or "")
    meta = out.get("meta") if isinstance(out.get("meta"), dict) else {}

    # Allow explicit override from ingestion for manual labels
    intent = out.get("intent_type")
    if not intent or intent not in {
        "problem", "question", "request", "complaint", "buying_intent",
        "workaround", "feature_request", "supply", "promotion", "news", "noise", "unknown",
    }:
        intent, conf = classify_intent(raw, meta=meta)
        out["intent_type"] = intent
        out["confidence"] = round(conf, 3)
    else:
        out.setdefault("confidence", 0.5)

    strength = out.get("evidence_strength")
    if strength not in ("strong", "medium", "weak", "invalid"):
        strength = assess_evidence_strength(out["intent_type"], raw)
        out["evidence_strength"] = strength

    q = out.get("qualification_status")
    if q not in ("qualified", "review", "rejected"):
        out["qualification_status"] = qualify(out["intent_type"], out["evidence_strength"])

    if "problem_statement" not in out or not out.get("problem_statement"):
        ps = extract_problem_statement(raw, out["intent_type"])
        if ps:
            out["problem_statement"] = ps

    # provenance for quality engine
    meta = dict(meta)
    meta.setdefault("quality_engine", "discovery.quality.v1")
    out["meta"] = meta
    return out


def is_opportunity_eligible(signal: dict[str, Any]) -> bool:
    """True only if qualified. Phase 3 should gate on this."""
    s = signal if signal.get("qualification_status") else apply_quality(dict(signal))
    return s.get("qualification_status") == "qualified"
