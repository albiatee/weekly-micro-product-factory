"""Phase 9 — human-gated Discovery Feedback (no auto Opportunity)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from analytics.pipeline import generate_learning_records  # noqa: E402
from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from discovery_feedback.pipeline import (  # noqa: E402
    approve_hint,
    convert_to_signal,
    create_hint_from_learning,
    reject_hint,
)
from discovery_feedback.store import list_hints  # noqa: E402
from experiment.pipeline import complete_experiment, record_results, start_experiment  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities  # noqa: E402


def _chain(tmp_path: Path):
    roots = {n: tmp_path / n for n in ("sig", "opp", "exp", "dec", "an", "hints")}
    for d in roots.values():
        d.mkdir()
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": (
                "Shop owners struggle every week reconciling invoices manually "
                "without a simple offline tool. [phase9-loop]"
            ),
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    sid = list(list_signals(roots["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = _exp_pipe.create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="m",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"])
    record_results(eid, metrics={"signups": 1}, experiments_root=roots["exp"])
    complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"])
    create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="Iterate to learn more from a follow-up experiment on the same problem domain.",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    generate_learning_records(
        opportunity_id=oid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        analytics_root=roots["an"],
    )
    from analytics.store import list_learnings

    lid = list(list_learnings(roots["an"]).keys())[0]
    return roots, lid, oid


def test_proposed_cannot_convert(tmp_path):
    roots, lid, _ = _chain(tmp_path)
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    assert h["status"] == "proposed"
    bad = convert_to_signal(
        h["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    )
    assert not bad.ok


def test_approve_then_convert_provenance(tmp_path):
    roots, lid, oid = _chain(tmp_path)
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    n_sig = len(list_signals(roots["sig"]))
    n_opp = len(list_opportunities(roots["opp"]))
    ap = approve_hint(h["id"], reviewed_by="alice", review_notes="worth exploring", hints_root=roots["hints"])
    assert ap.ok
    assert ap.hint["status"] == "approved"
    assert ap.hint["reviewed_by"] == "alice"
    assert ap.hint.get("converted_signal_id") is None
    cr = convert_to_signal(
        h["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    )
    assert cr.ok, cr.errors
    assert cr.signal["id"].startswith("sig_")
    assert cr.signal["meta"]["discovery_hint_id"] == h["id"]
    assert len(list_signals(roots["sig"])) == n_sig + 1
    assert len(list_opportunities(roots["opp"])) == n_opp  # no auto opportunity


def test_reject_blocks_convert(tmp_path):
    roots, lid, _ = _chain(tmp_path)
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    reject_hint(h["id"], reviewed_by="bob", hints_root=roots["hints"])
    assert not convert_to_signal(
        h["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    ).ok


def test_duplicate_hint_idempotent(tmp_path):
    roots, lid, _ = _chain(tmp_path)
    r1 = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    )
    r2 = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    )
    assert r1.ok
    assert not r2.ok
    assert len(list_hints(roots["hints"])) == 1
