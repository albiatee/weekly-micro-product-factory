"""Phase 9 — Discovery Feedback tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from analytics.pipeline import generate_learning_records  # noqa: E402
from analytics.store import list_learnings  # noqa: E402
from decision.pipeline import create_decision  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from discovery_feedback.pipeline import (  # noqa: E402
    accept_hint,
    create_hint_from_learning,
    defer_hint,
    reject_hint,
)
from discovery_feedback.store import list_hints  # noqa: E402
from discovery_feedback.validate import validate_hint_transition  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals as list_sig  # noqa: E402
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
    d = {}
    for n in ("sig", "opp", "exp", "dec", "an", "hints"):
        p = tmp_path / n
        p.mkdir()
        d[n] = p
    return d


def _learning(roots) -> str:
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_discovery_feedback-10]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    from discovery.store import list_signals as ls

    sid = list(ls(roots["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = _exp_pipe.create_experiment(
        oid, experiment_type="waitlist", measurement_plan="m",
        opportunities_root=roots["opp"], experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"])
    record_results(eid, metrics={"signups": 1}, experiments_root=roots["exp"])
    complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"])
    create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="Iterate to learn more from a follow-up experiment on the same problem",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    lr = generate_learning_records(
        opportunity_id=oid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        distribution_root=None,
        analytics_root=roots["an"],
    )
    assert lr.learnings
    return lr.learnings[0]["id"]


def test_create_hint_from_learning(roots):
    lid = _learning(roots)
    res = create_hint_from_learning(
        lid,
        learnings_root=roots["an"],
        opportunities_root=roots["opp"],
        hints_root=roots["hints"],
    )
    assert res.ok, res.errors
    assert res.hint["id"].startswith("dh_")
    assert res.hint["status"] == "proposed"
    assert res.hint["source_learning_id"] == lid


def test_missing_learning(roots):
    res = create_hint_from_learning(
        "lr_missing",
        learnings_root=roots["an"],
        opportunities_root=roots["opp"],
        hints_root=roots["hints"],
    )
    assert not res.ok


def test_duplicate_hint(roots):
    lid = _learning(roots)
    assert create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).ok
    assert not create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).ok


def test_accept_creates_signal_not_opportunity(roots):
    lid = _learning(roots)
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    n_opp_before = len(list_opportunities(roots["opp"]))
    res = accept_hint(
        h["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    )
    assert res.ok, res.errors
    assert res.hint["status"] == "accepted"
    assert res.signal["id"].startswith("sig_")
    assert res.signal["meta"]["source_detail"] == "discovery_feedback"
    assert res.signal["meta"]["discovery_hint_id"] == h["id"]
    assert len(list_opportunities(roots["opp"])) == n_opp_before
    assert "market proven" not in res.signal["raw_text"].lower()


def test_reject_and_transitions(roots):
    lid = _learning(roots)
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    assert reject_hint(h["id"], hints_root=roots["hints"]).ok
    assert not accept_hint(
        h["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    ).ok
    assert not validate_hint_transition("rejected", "accepted").ok
    assert not validate_hint_transition("accepted", "proposed").ok


def test_defer(roots):
    lid = _learning(roots)
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    assert defer_hint(h["id"], hints_root=roots["hints"]).ok
    assert list_hints(roots["hints"])[h["id"]]["status"] == "deferred"


def test_dry_run(roots):
    lid = _learning(roots)
    res = create_hint_from_learning(
        lid,
        learnings_root=roots["an"],
        opportunities_root=roots["opp"],
        hints_root=roots["hints"],
        dry_run=True,
    )
    assert res.ok
    assert list_hints(roots["hints"]) == {}
    # persist for accept dry-run
    res = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    )
    sig_before = set(list_sig(roots["sig"]).keys())
    ar = accept_hint(
        res.hint["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
        dry_run=True,
    )
    assert ar.ok
    assert set(list_sig(roots["sig"]).keys()) == sig_before
    assert list_hints(roots["hints"])[res.hint["id"]]["status"] == "proposed"
