"""Phase 3 — Opportunity Evidence model & readiness."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.normalize import candidate_to_signal_dict  # noqa: E402
from discovery.quality import apply_quality  # noqa: E402
from discovery.sources.base import RawSignalCandidate  # noqa: E402
from opportunity.evidence import (  # noqa: E402
    attach_evidence_layer,
    is_evidence_ready,
)
from opportunity.generate import build_opportunity_from_signals  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402


def _qualified_signal(text: str, sid: str) -> dict:
    c = RawSignalCandidate(source="manual", raw_text=text)
    s = candidate_to_signal_dict(c, signal_id=sid)
    s = apply_quality(s)
    s["intent_type"] = "problem"
    s["evidence_strength"] = "medium"
    s["qualification_status"] = "qualified"
    return s


def test_single_signal_opportunity_has_evidence():
    s = _qualified_signal(
        "Shop owners struggle every week reconciling invoices manually without offline tools.",
        "sig_evtest00000001",
    )
    opp = build_opportunity_from_signals([s])
    assert opp["signal_ids"] == [s["id"]]
    assert isinstance(opp["evidence"], list) and len(opp["evidence"]) >= 1
    assert opp["evidence"][0]["signal_id"] == s["id"]
    assert opp["assumptions"]
    assert opp["unknowns"]
    ok, errs = is_evidence_ready(opp)
    assert ok, errs


def test_multi_signal_traceable():
    s1 = _qualified_signal(
        "Freelancers waste hours every week matching payments manually.",
        "sig_evtest00000002",
    )
    s2 = _qualified_signal(
        "Small shops cannot afford SaaS invoicing and use spreadsheets as workaround.",
        "sig_evtest00000003",
    )
    opp = build_opportunity_from_signals([s1, s2])
    assert set(opp["signal_ids"]) == {s1["id"], s2["id"]}
    refs = {e.get("signal_id") for e in opp["evidence"] if e.get("signal_id")}
    assert s1["id"] in refs and s2["id"] in refs


def test_no_signal_not_ready():
    opp = {
        "id": "opp_x",
        "problem": "Some problem statement that is long enough here",
        "audience": "shops",
        "signal_ids": [],
        "evidence": [],
        "assumptions": [],
        "unknowns": [],
    }
    ok, errs = is_evidence_ready(opp)
    assert not ok
    assert any("signal" in e for e in errs)


def test_missing_problem_not_ready():
    opp = {
        "problem": "x",
        "audience": "devs",
        "signal_ids": ["sig_aaaaaaaaaaaaaaaa"],
        "evidence": [
            {"signal_id": "sig_aaaaaaaaaaaaaaaa", "summary": "note"}
        ],
        "assumptions": [],
        "unknowns": [],
    }
    ok, _ = is_evidence_ready(opp)
    assert not ok


def test_missing_target_not_ready():
    opp = {
        "problem": "A sufficiently long problem statement about invoices",
        "audience": "",
        "signal_ids": ["sig_aaaaaaaaaaaaaaaa"],
        "evidence": [
            {"signal_id": "sig_aaaaaaaaaaaaaaaa", "summary": "pain"}
        ],
        "assumptions": [],
        "unknowns": [],
    }
    ok, errs = is_evidence_ready(opp)
    assert not ok
    assert any("target" in e or "audience" in e for e in errs)


def test_evidence_without_reference_not_ready():
    opp = {
        "problem": "A sufficiently long problem statement about invoices",
        "audience": "shops",
        "signal_ids": ["sig_aaaaaaaaaaaaaaaa"],
        "evidence": [{"summary": "claim without source"}],
        "assumptions": [],
        "unknowns": [],
    }
    ok, errs = is_evidence_ready(opp)
    assert not ok
    assert any("signal_id" in e for e in errs)


def test_assumption_not_in_evidence_list():
    s = _qualified_signal(
        "Teams struggle daily with broken CI pipelines wasting runner time.",
        "sig_evtest00000004",
    )
    opp = build_opportunity_from_signals([s])
    for a in opp["assumptions"]:
        assert "pay" in a["assumption"].lower() or "frequen" in a["assumption"].lower()
    # assumptions are separate structure
    assert "assumptions" in opp
    assert all("assumption" in a for a in opp["assumptions"])


def test_unknowns_present_without_invention():
    s = _qualified_signal(
        "Users cannot disable invasive OS assistants and struggle with privacy settings.",
        "sig_evtest00000005",
    )
    opp = build_opportunity_from_signals([s])
    assert any("pay" in u.lower() or "willing" in u.lower() for u in opp["unknowns"])


def test_strong_signal_not_auto_validated():
    s = _qualified_signal(
        "I waste hours every day on manual inventory counts without barcode tools.",
        "sig_evtest00000006",
    )
    s["evidence_strength"] = "strong"
    opp = build_opportunity_from_signals([s])
    # Opportunity evidence_strength should not claim market validation
    assert opp.get("evidence_strength") in ("weak", "medium", "none")
    assert "not market validation" in (opp.get("notes") or "").lower() or "Phase 3" in (
        opp.get("notes") or ""
    )


def test_pipeline_generates_evidence(tmp_path: Path):
    s = _qualified_signal(
        "Clinic staff struggle every week because appointment tools fail offline and they work around with paper.",
        "sig_evtest00000007",
    )
    r = generate_from_signal_ids(
        [s["id"]],
        signals_map={s["id"]: s},
        opportunities_root=tmp_path / "opp",
        dry_run=True,
        created_by="tester",
    )
    assert r.accepted, r.rejected
    opp = r.accepted[0]["opportunity"]
    ok, errs = is_evidence_ready(opp)
    assert ok, errs
