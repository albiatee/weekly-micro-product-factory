"""Phase 11 — hardening: negative paths, gates, idempotency, human gates.

Does not change product behavior; asserts existing invariants.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals, upsert_signal  # noqa: E402
from discovery_feedback.pipeline import (  # noqa: E402
    approve_hint,
    convert_to_signal,
    create_hint_from_learning,
    defer_hint,
    reject_hint,
)
from distribution.from_spec import create_distribution_from_spec  # noqa: E402
from experiment.pipeline import (  # noqa: E402
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities, upsert_opportunity  # noqa: E402
from production.pipeline import create_production_spec  # noqa: E402
from production.spec import is_production_ready  # noqa: E402


PROBLEM_TEXT = (
    "Shop owners struggle every week reconciling invoices manually "
    "without a simple offline tool. [phase11-hardening]"
)


def _mk(tmp_path: Path) -> dict[str, Path]:
    roots = {n: tmp_path / n for n in ("sig", "opp", "exp", "dec", "prd", "dist", "an", "hints")}
    for d in roots.values():
        d.mkdir()
    return roots


def _qualified_signal(roots: dict[str, Path]) -> str:
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": PROBLEM_TEXT,
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    return list(list_signals(roots["sig"]).keys())[0]


def test_unqualified_signal_cannot_generate_opportunity(tmp_path):
    roots = _mk(tmp_path)
    sid = _qualified_signal(roots)
    sig = list_signals(roots["sig"])[sid]
    # Force review status (bypass would be invalid for opportunity generation)
    sig = {**sig, "qualification_status": "review"}
    upsert_signal(sig, roots["sig"])
    g = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    )
    assert not g.accepted
    assert list_opportunities(roots["opp"]) == {} or not any(
        sid in (o.get("signal_ids") or []) for o in list_opportunities(roots["opp"]).values()
    )


def test_incomplete_experiment_cannot_decide(tmp_path):
    roots = _mk(tmp_path)
    sid = _qualified_signal(roots)
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count synthetic signups",
        success_criteria=">=10 synthetic signups",
        failure_criteria="<3 synthetic signups",
        target_population="shop owners",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    assert er.ok
    eid = er.experiment["id"]
    # still planned — not completed
    dres = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="Attempt decision before experiment completion should fail the gate.",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    assert not dres.ok
    assert any("completed" in e.lower() or "status" in e.lower() for e in dres.errors)


def test_iterate_cannot_create_production_spec(tmp_path):
    roots = _mk(tmp_path)
    sid = _qualified_signal(roots)
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count synthetic waitlist signups over 14 days",
        success_criteria="At least 10 synthetic pilot signups recorded",
        failure_criteria="Fewer than 3 synthetic pilot signups recorded",
        target_population="Small shop owners (hardening fixture)",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    assert start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"]).ok
    assert record_results(eid, metrics={"signups": 1}, experiments_root=roots["exp"]).ok
    assert complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"]).ok
    dres = create_decision(
        opportunity_id=oid,
        verdict="iterate",
        reason="Iterate verdict must not authorize production specification creation.",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    assert dres.ok
    pres = create_production_spec(
        decision_id=dres.decision["id"],
        opportunities_root=roots["opp"],
        decisions_root=roots["dec"],
        experiments_root=roots["exp"],
        production_root=roots["prd"],
    )
    assert not pres.ok
    assert any("execute" in e for e in pres.errors)


def test_kill_cannot_create_production_spec(tmp_path):
    roots = _mk(tmp_path)
    sid = _qualified_signal(roots)
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count synthetic waitlist signups over 14 days",
        success_criteria="At least 10 synthetic pilot signups recorded",
        failure_criteria="Fewer than 3 synthetic pilot signups recorded",
        target_population="Small shop owners (hardening fixture)",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    assert start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"]).ok
    assert record_results(eid, metrics={"signups": 0}, experiments_root=roots["exp"]).ok
    assert complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"]).ok
    dres = create_decision(
        opportunity_id=oid,
        verdict="kill",
        reason="Kill verdict must not authorize production specification.",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    assert dres.ok
    ok, errs = is_production_ready(dres.decision, list_opportunities(roots["opp"])[oid], er.experiment)
    # experiment may need refresh as completed
    from experiment.store import get_experiment

    exp = get_experiment(eid, roots["exp"])
    ok, errs = is_production_ready(dres.decision, list_opportunities(roots["opp"])[oid], exp)
    assert not ok


def test_feedback_unapproved_rejected_deferred_cannot_convert(tmp_path):
    roots = _mk(tmp_path)
    # Minimal learning via e2e-like path abbreviated: create learning from decision
    from analytics.pipeline import generate_learning_records
    from analytics.store import list_learnings

    sid = _qualified_signal(roots)
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er = create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count synthetic waitlist signups over 14 days",
        success_criteria="At least 10 synthetic pilot signups recorded",
        failure_criteria="Fewer than 3 synthetic pilot signups recorded",
        target_population="Small shop owners (hardening fixture)",
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
        reason="Need more evidence before any production planning for this pilot case.",
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
    lid = list(list_learnings(roots["an"]).keys())[0]
    h = create_hint_from_learning(
        lid, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint

    # proposed
    assert not convert_to_signal(
        h["id"], hints_root=roots["hints"], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).ok

    # rejected
    reject_hint(h["id"], reviewed_by="human", hints_root=roots["hints"])
    assert not convert_to_signal(
        h["id"], hints_root=roots["hints"], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).ok

    # new hint for defer
    # force new text path by using same learning after reject status allows? dedup blocks
    # create second learning-based: build new hint id by rejecting first - need different learning
    # For deferred: create fresh chain is heavy; use approve path reverse
    # Create another opportunity path is expensive - use approve then we need deferred from proposed
    # New signal text variant
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": PROBLEM_TEXT + " variant-defer",
            "captured_at": "2026-09-20T13:00:00Z",
        },
        store_root=roots["sig"],
    )
    sid2 = [k for k in list_signals(roots["sig"]) if k != sid][0]
    oid2 = generate_from_signal_ids(
        [sid2], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    er2 = create_experiment(
        oid2,
        experiment_type="waitlist",
        measurement_plan="Count synthetic waitlist signups variant over 14 days",
        success_criteria="At least 10 synthetic pilot signups recorded variant",
        failure_criteria="Fewer than 3 synthetic pilot signups recorded variant",
        target_population="Small shop owners variant (hardening fixture)",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    eid2 = er2.experiment["id"]
    start_experiment(eid2, opportunities_root=roots["opp"], experiments_root=roots["exp"])
    record_results(eid2, metrics={"signups": 2}, experiments_root=roots["exp"])
    complete_experiment(eid2, experiments_root=roots["exp"], opportunities_root=roots["opp"])
    create_decision(
        opportunity_id=oid2,
        verdict="iterate",
        reason="Second iterate case for deferred feedback conversion rejection test.",
        evidence_refs=[eid2],
        decided_by="human",
        experiment_id=eid2,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    generate_learning_records(
        opportunity_id=oid2,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        analytics_root=roots["an"],
    )
    lid2 = [k for k in list_learnings(roots["an"]) if k != lid][0]
    h2 = create_hint_from_learning(
        lid2, learnings_root=roots["an"], opportunities_root=roots["opp"], hints_root=roots["hints"]
    ).hint
    defer_hint(h2["id"], reviewed_by="human", hints_root=roots["hints"])
    assert not convert_to_signal(
        h2["id"], hints_root=roots["hints"], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).ok


def test_decision_opportunity_mismatch_rejected(tmp_path):
    roots = _mk(tmp_path)
    ok, errs = is_production_ready(
        {"id": "dec_x", "verdict": "execute", "opportunity_id": "opp_a", "experiment_id": "exp_x"},
        {"id": "opp_b", "status": "building"},
        {"id": "exp_x", "status": "completed", "opportunity_id": "opp_a"},
    )
    assert not ok
    assert any("mismatch" in e for e in errs)


def test_distribution_requires_production_spec(tmp_path):
    roots = _mk(tmp_path)
    res = create_distribution_from_spec(
        "prd_doesnotexist000",
        channel="landing_page",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert not res["ok"]


def test_confidence_cannot_bypass_human_review(tmp_path):
    """Even high confidence string on a proposed hint does not allow convert."""
    roots = _mk(tmp_path)
    from discovery_feedback.store import list_hints, upsert_hint

    # Minimal fake approved path requires learning — use stored proposed with confidence high
    sid = _qualified_signal(roots)
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    # inject proposed hint without full learning (validate may need learning id)
    from discovery_feedback.build import generate_hint_id
    from discovery_feedback.validate import validate_hint

    now = "2026-09-20T12:00:00Z"
    h = {
        "id": generate_hint_id(),
        "opportunity_id": oid,
        "hint": "Follow-up discovery candidate (not market proof)",
        "status": "proposed",
        "source_learning_id": "lr_aaaaaaaaaaaaaaaa",
        "confidence": "high",
        "created_at": now,
        "updated_at": now,
        "created_by": "system",
    }
    # may fail validate if strict — still test convert gate
    upsert_hint(h, roots["hints"])
    res = convert_to_signal(
        h["id"],
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    )
    assert not res.ok
