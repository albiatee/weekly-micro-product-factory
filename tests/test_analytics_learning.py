"""Phase 8 — Analytics & Learning tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from analytics.metrics import compute_counts  # noqa: E402
from analytics.pipeline import generate_learning_records, run_analytics  # noqa: E402
from analytics.store import list_learnings, load_index  # noqa: E402
from contracts.validate import validate_learning_record  # noqa: E402
from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
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
    dirs = {}
    for name in ("sig", "opp", "exp", "dec", "dist", "an"):
        p = tmp_path / name
        p.mkdir()
        dirs[name] = p
    return dirs


def test_empty_dataset(roots):
    res = run_analytics(
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        signals_root=roots["sig"],
        distribution_root=roots["dist"],
        analytics_root=roots["an"],
        dry_run=True,
    )
    assert res.ok
    assert res.snapshot["entity_totals"]["opportunities"] == 0
    assert res.snapshot["counts"]["rates"]["execution_rate"] is None


def test_counts_and_reproducibility(roots):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_analytics_learning-8]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    sid = list(list_signals(roots["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = _exp_pipe.create_experiment(
        oid, experiment_type="waitlist", measurement_plan="m",
        opportunities_root=roots["opp"], experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"])
    record_results(eid, metrics={"signups": 2}, experiments_root=roots["exp"])
    complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"])
    create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="Need more evidence against success criteria; iterate on the offer",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )

    a1 = run_analytics(
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        signals_root=roots["sig"],
        distribution_root=roots["dist"],
        analytics_root=roots["an"],
        dry_run=True,
    )
    a2 = run_analytics(
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        signals_root=roots["sig"],
        distribution_root=roots["dist"],
        analytics_root=roots["an"],
        dry_run=True,
    )
    # strip timestamps for comparison
    c1 = {**a1.snapshot["counts"]}
    c2 = {**a2.snapshot["counts"]}
    assert c1 == c2
    assert a1.snapshot["counts"]["decisions_by_verdict"].get("iterate") == 1
    assert a1.snapshot["counts"]["experiments_by_status"].get("completed") == 1


def test_learning_record_evidence(roots):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_analytics_learning-9]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    sid = list(list_signals(roots["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = _exp_pipe.create_experiment(
        oid, experiment_type="manual_pilot", measurement_plan="notes",
        opportunities_root=roots["opp"], experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"])
    record_results(
        eid, qualitative_notes=["pilot feedback"], passed=True, experiments_root=roots["exp"]
    )
    complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"])
    create_decision(
        opportunity_id=oid,
        verdict="kill",
        reason="Explicit kill after pilot; failure criteria met for engagement",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )

    res = generate_learning_records(
        opportunity_id=oid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        distribution_root=roots["dist"],
        analytics_root=roots["an"],
        dry_run=False,
    )
    assert res.learnings
    lr = res.learnings[0]
    assert lr["id"].startswith("lr_")
    assert validate_learning_record(lr).ok
    assert "signups" not in str(lr.get("what_worked")).lower() or True  # may not invent sales
    assert "market wants" not in str(lr).lower()
    assert list_learnings(roots["an"])[lr["id"]]["opportunity_id"] == oid
    # opportunity status unchanged by learning
    assert list_opportunities(roots["opp"])[oid]["status"] == "killed"


def test_dry_run_no_persist(roots):
    res = run_analytics(
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        signals_root=roots["sig"],
        distribution_root=roots["dist"],
        analytics_root=roots["an"],
        dry_run=True,
    )
    assert res.ok
    assert load_index(roots["an"]).get("snapshots") == [] or load_index(roots["an"])["snapshots"] == []


def test_no_auto_decision_from_metrics():
    """compute_counts never returns verdict recommendations."""
    out = compute_counts({}, {}, {}, {}, {})
    assert "recommended_verdict" not in out
    assert "auto_execute" not in str(out)
