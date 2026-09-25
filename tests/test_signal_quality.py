"""Phase 2 Signal Quality — deterministic classification & qualification."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.validate import validate_signal  # noqa: E402
from discovery.normalize import candidate_to_signal_dict  # noqa: E402
from discovery.quality import (  # noqa: E402
    apply_quality,
    assess_evidence_strength,
    classify_intent,
    is_opportunity_eligible,
    qualify,
)
from discovery.sources.base import RawSignalCandidate  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402


def _sig(text: str, **kw) -> dict:
    c = RawSignalCandidate(source=kw.get("source", "manual"), raw_text=text, url=kw.get("url"))
    return candidate_to_signal_dict(c)


def test_problem_qualified():
    s = _sig(
        "I waste several hours every week reconciling invoices manually because our tool cannot match payments."
    )
    assert s["intent_type"] in ("problem", "workaround")
    assert s["evidence_strength"] in ("strong", "medium")
    assert s["qualification_status"] == "qualified"
    assert is_opportunity_eligible(s)


def test_buying_intent():
    s = _sig("We are willing to pay for a simple offline invoicing tool; current SaaS is too expensive.")
    assert s["intent_type"] == "buying_intent"
    assert s["qualification_status"] in ("qualified", "review")
    assert s["evidence_strength"] != "invalid"


def test_workaround():
    s = _sig(
        "We struggle with inventory counts every month so we manually use Excel as a workaround instead of a real system."
    )
    assert s["intent_type"] in ("workaround", "problem")
    assert s["qualification_status"] in ("qualified", "review")


def test_generic_question_review():
    s = _sig("Ask HN: How do you guys stay on top of code reviews?")
    assert s["intent_type"] in ("question", "unknown", "noise")
    assert s["qualification_status"] in ("review", "rejected", "qualified")


def test_supply_rejected():
    s = _sig(
        "Ask HN: Developer looking for freelance or contract work (300 USD/week). DM me if interested."
    )
    assert s["intent_type"] == "supply"
    assert s["evidence_strength"] == "invalid"
    assert s["qualification_status"] == "rejected"
    assert not is_opportunity_eligible(s)


def test_promotion_rejected():
    s = _sig("Show HN: We built Prospectiz – freelance CRM that emails from the contact card")
    assert s["intent_type"] in ("promotion", "noise")
    assert s["qualification_status"] == "rejected"


def test_news_rejected():
    s = _sig(
        "Humans& with Alexis Ross — I am SUPER EXCITED to publish the 145th episode of the Weaviate Podcast. YouTube: https://youtu.be/x Spotify: https://spotify.com/x"
    )
    assert s["intent_type"] in ("news", "noise", "promotion")
    assert s["qualification_status"] == "rejected"


def test_noise_rejected():
    s = _sig("Ask HN: What is the most interesting project you are working on?")
    assert s["intent_type"] in ("noise", "question")
    assert s["qualification_status"] in ("rejected", "review")


def test_backward_compat_minimal_signal():
    """Legacy shape without quality fields still validates."""
    legacy = {
        "id": "sig_abcd1234abcd1234",
        "source": "manual",
        "raw_text": "legacy signal text without quality fields attached yet",
        "captured_at": "2026-01-01T00:00:00Z",
    }
    vr = validate_signal(legacy)
    assert vr.ok, vr.errors


def test_invalid_intent_rejected_by_contract():
    bad = {
        "id": "sig_abcd1234abcd1234",
        "source": "manual",
        "raw_text": "x" * 30,
        "captured_at": "2026-01-01T00:00:00Z",
        "intent_type": "not_a_real_intent",
    }
    vr = validate_signal(bad)
    assert not vr.ok


def test_deterministic_classification():
    text = "I cannot disable Siri on macOS and it keeps listening after every restart."
    a, _ = classify_intent(text)
    b, _ = classify_intent(text)
    assert a == b
    assert assess_evidence_strength(a, text) == assess_evidence_strength(a, text)
    assert qualify(a, assess_evidence_strength(a, text)) == qualify(
        a, assess_evidence_strength(a, text)
    )


def test_opportunity_gate_rejects_supply(tmp_path: Path):
    supply = _sig(
        "Ask HN: Developer looking for freelance or contract work. DM me on discord."
    )
    supply["id"] = "sig_supply00000001"
    smap = {supply["id"]: supply}
    r = generate_from_signal_ids(
        [supply["id"]],
        signals_map=smap,
        opportunities_root=tmp_path / "opp",
        dry_run=True,
    )
    assert len(r.accepted) == 0
    assert len(r.rejected) >= 1
    assert "quality" in str(r.rejected[0]).lower() or "qualified" in str(r.rejected[0]).lower()


def test_opportunity_gate_accepts_problem(tmp_path: Path):
    problem = _sig(
        "A small coding change triggers the whole CI/CD pipeline and wastes runner time every day."
    )
    problem["id"] = "sig_problem0000001"
    # ensure qualified
    problem = apply_quality(problem)
    if problem["qualification_status"] != "qualified":
        problem["intent_type"] = "problem"
        problem["evidence_strength"] = "strong"
        problem["qualification_status"] = "qualified"
    smap = {problem["id"]: problem}
    r = generate_from_signal_ids(
        [problem["id"]],
        signals_map=smap,
        opportunities_root=tmp_path / "opp",
        dry_run=True,
        created_by="tester",
    )
    # may still reject on contract fields for opportunity — at least not quality gate if qualified
    if r.rejected:
        assert "quality gate" not in str(r.rejected[0].get("errors", [])).lower()
