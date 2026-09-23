"""Phase 5 — Decision Gate tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.validate import validate_decision  # noqa: E402
from decision.pipeline import create_decision  # noqa: E402
from decision.store import list_decisions  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from experiment.pipeline import (  # noqa: E402
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities  # noqa: E402


@pytest.fixture
def roots(tmp_path: Path):
    sig = tmp_path / "signals"
    opp = tmp_path / "opportunities"
    exp = tmp_path / "experiments"
    dec = tmp_path / "decisions"
    for d in (sig, opp, exp, dec):
        d.mkdir()
    return sig, opp, exp, dec


def _ready_experimenting(sig, opp, exp):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Need offline checklist for shops",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=sig,
    )
    from discovery.store import list_signals

    sid = list(list_signals(sig).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=sig, opportunities_root=opp
    ).accepted[0]["opportunity"]["id"]
    er = create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count signups over 7 days",
        opportunities_root=opp,
        experiments_root=exp,
    )
    eid = er.experiment["id"]
    assert start_experiment(eid, opportunities_root=opp, experiments_root=exp).ok
    assert record_results(
        eid, metrics={"signups": 5}, qualitative_notes=["shared in group"], experiments_root=exp
    ).ok
    assert complete_experiment(eid, experiments_root=exp, opportunities_root=opp).ok
    return oid, eid


def test_valid_execute_decision(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="Completed waitlist experiment recorded interest signals worth a build attempt",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert res.ok, res.errors
    assert res.decision["id"].startswith("dec_")
    assert validate_decision(res.decision).ok
    assert res.opportunity["status"] == "building"
    assert res.opportunity["latest_decision_id"] == res.decision["id"]
    assert res.decision["id"] in list_decisions(dec)


def test_iterate_and_kill(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="Results too weak; revise hypothesis",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert res.ok, res.errors
    assert res.opportunity["status"] == "iterating"


def test_kill_verdict(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="kill",
        reason="No meaningful engagement in completed experiment",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert res.ok, res.errors
    assert res.opportunity["status"] == "killed"


def test_missing_evidence_rejected(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="no evidence",
        evidence_refs=[],
        decided_by="human",
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert not res.ok


def test_nonexistent_exp_rejected(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="fake",
        evidence_refs=["exp_does_not_exist"],
        decided_by="human",
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert not res.ok


def test_invalid_evidence_prefix(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="bad ref",
        evidence_refs=["lr_1"],
        decided_by="human",
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert not res.ok


def test_hypothesized_cannot_decide(roots):
    sig, opp, exp, dec = roots
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "another signal text",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=sig,
    )
    from discovery.store import list_signals

    sid = list(list_signals(sig).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=sig, opportunities_root=opp
    ).accepted[0]["opportunity"]["id"]
    res = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="skip experiment",
        evidence_refs=["exp_x"],
        decided_by="human",
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert not res.ok
    assert any("status" in e for e in res.errors)


def test_duplicate_decision_refused(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    r1 = create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="first decision",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert r1.ok
    r2 = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="second",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert not r2.ok


def test_agent_suggestion_does_not_override_verdict(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="kill",
        reason="Human rejects despite agent optimism",
        evidence_refs=[eid],
        decided_by="human_with_agent_suggestion",
        experiment_id=eid,
        agent_suggestion="execute",
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert res.ok, res.errors
    assert res.decision["verdict"] == "kill"
    assert res.decision["agent_suggestion"] == "execute"
    assert res.opportunity["status"] == "killed"


def test_dry_run_no_persist(roots):
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    res = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="dry",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
        dry_run=True,
    )
    assert res.ok
    assert list_decisions(dec) == {}
    assert list_opportunities(opp)[oid]["status"] == "experimenting"


def test_no_auto_from_passed_alone(roots):
    """Creating decision still requires explicit verdict — pipeline never reads passed."""
    sig, opp, exp, dec = roots
    oid, eid = _ready_experimenting(sig, opp, exp)
    # Explicit kill even if experiment had passed=true potential
    res = create_decision(
        opportunity_id=oid,
        verdict="kill",
        reason="Explicit human kill despite any passed flag",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    assert res.ok
    assert res.opportunity["status"] == "killed"
