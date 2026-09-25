"""Phase 4 — Validation Experiments tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.validate import validate_experiment  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from experiment.lifecycle import validate_experiment_transition  # noqa: E402
_CRIT = dict(
    success_criteria={"metric": "signups", "min": 1, "window": "test"},
    failure_criteria={"metric": "signups", "max_below": 1, "window": "test"},
    target_population="Users who reported the stated problem in source signals",
)

from experiment.pipeline import (  # noqa: E402
    abort_experiment,
    complete_experiment,
    record_results,
    start_experiment,
)
from experiment.store import list_experiments  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities  # noqa: E402


@pytest.fixture
def roots(tmp_path: Path):
    sig = tmp_path / "signals"
    opp = tmp_path / "opportunities"
    exp = tmp_path / "experiments"
    for d in (sig, opp, exp):
        d.mkdir()
    return sig, opp, exp


def _seed_opportunity(sig_store, opp_store):
    r = ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_experiments-0]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=sig_store,
    )
    sid = r.accepted[0]["signal"]["id"]
    g = generate_from_signal_ids(
        [sid], signals_root=sig_store, opportunities_root=opp_store
    )
    return g.accepted[0]["opportunity"]



def create_experiment(*args, **kwargs):
    from experiment import pipeline as _p
    kwargs.setdefault("success_criteria", _CRIT["success_criteria"])
    kwargs.setdefault("failure_criteria", _CRIT["failure_criteria"])
    kwargs.setdefault("target_population", _CRIT["target_population"])
    return _p.create_experiment(*args, **kwargs)

def test_valid_experiment_create(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="waitlist",
        measurement_plan="Count signups 7 days",
        opportunities_root=opp,
        experiments_root=exp,
    )
    assert res.ok, res.errors
    assert res.experiment["id"].startswith("exp_")
    assert res.experiment["status"] == "planned"
    assert res.experiment["opportunity_id"] == o["id"]
    assert validate_experiment(res.experiment).ok


def test_invalid_experiment_type(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="not_a_type",
        opportunities_root=opp,
        experiments_root=exp,
    )
    assert not res.ok


def test_missing_opportunity(roots):
    _, opp, exp = roots
    res = create_experiment(
        "opp_missing",
        experiment_type="smoke_page",
        opportunities_root=opp,
        experiments_root=exp,
    )
    assert not res.ok


def test_lifecycle_transitions():
    assert validate_experiment_transition("planned", "running").ok
    assert validate_experiment_transition("running", "completed").ok
    assert validate_experiment_transition("planned", "aborted").ok
    assert validate_experiment_transition("running", "aborted").ok
    assert not validate_experiment_transition("planned", "completed").ok
    assert not validate_experiment_transition("completed", "running").ok
    assert not validate_experiment_transition("aborted", "running").ok


def test_start_requires_measurement_plan(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"], experiment_type="manual_pilot", opportunities_root=opp, experiments_root=exp
    )
    eid = res.experiment["id"]
    bad = start_experiment(eid, opportunities_root=opp, experiments_root=exp)
    assert not bad.ok
    good = start_experiment(
        eid,
        measurement_plan="Log pilot conversations for 5 days",
        opportunities_root=opp,
        experiments_root=exp,
    )
    assert good.ok, good.errors
    assert good.experiment["status"] == "running"
    assert good.opportunity["status"] == "experimenting"
    assert good.opportunity["active_experiment_id"] == eid


def test_measurement_plan_object_accepted(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="smoke_page",
        measurement_plan={"metric": "cta_clicks", "window_days": 7},
        opportunities_root=opp,
        experiments_root=exp,
    )
    assert res.ok
    st = start_experiment(res.experiment["id"], opportunities_root=opp, experiments_root=exp)
    assert st.ok, st.errors


def test_empty_measurement_plan_rejected_at_running(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="waitlist",
        measurement_plan="",
        opportunities_root=opp,
        experiments_root=exp,
    )
    # may accept at planned; start must fail
    eid = res.experiment["id"] if res.ok else None
    if eid:
        st = start_experiment(eid, opportunities_root=opp, experiments_root=exp)
        assert not st.ok


def test_threshold_optional(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="preorder",
        measurement_plan="Track preorder button clicks",
        opportunities_root=opp,
        experiments_root=exp,
    )
    assert res.ok
    assert "success_threshold" not in res.experiment or res.experiment.get("success_threshold") is None


def test_record_and_complete(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="waitlist",
        measurement_plan="signups",
        opportunities_root=opp,
        experiments_root=exp,
    )
    eid = res.experiment["id"]
    assert start_experiment(eid, opportunities_root=opp, experiments_root=exp).ok
    assert not complete_experiment(eid, experiments_root=exp, opportunities_root=opp).ok
    rec = record_results(
        eid, metrics={"signups": 4}, qualitative_notes=["posted in forum"], passed=True,
        experiments_root=exp,
    )
    assert rec.ok, rec.errors
    done = complete_experiment(eid, experiments_root=exp, opportunities_root=opp)
    assert done.ok, done.errors
    assert done.experiment["status"] == "completed"
    # No Decision / not decided
    opps = list_opportunities(opp)
    assert opps[o["id"]]["status"] == "experimenting"
    assert "latest_decision_id" not in opps[o["id"]] or not opps[o["id"]].get("latest_decision_id")


def test_abort_does_not_kill_opportunity(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="community_vote",
        measurement_plan="Count 👍 reactions (supporting signal only)",
        opportunities_root=opp,
        experiments_root=exp,
    )
    eid = res.experiment["id"]
    start_experiment(eid, opportunities_root=opp, experiments_root=exp)
    ab = abort_experiment(eid, reason="insufficient reach", experiments_root=exp, opportunities_root=opp)
    assert ab.ok
    assert ab.experiment["status"] == "aborted"
    assert list_opportunities(opp)[o["id"]]["status"] != "killed"


def test_all_experiment_types_create(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    for t in (
        "smoke_page",
        "waitlist",
        "concierge",
        "preorder",
        "community_vote",
        "manual_pilot",
    ):
        r = create_experiment(
            o["id"],
            experiment_type=t,
            measurement_plan=f"Plan for {t}",
            opportunities_root=opp,
            experiments_root=exp,
        )
        assert r.ok, (t, r.errors)


def test_dry_run_create_no_store(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"],
        experiment_type="smoke_page",
        measurement_plan="clicks",
        opportunities_root=opp,
        experiments_root=exp,
        dry_run=True,
    )
    assert res.ok
    assert list_experiments(exp) == {}


def test_no_decision_keys_on_complete(roots):
    sig, opp, exp = roots
    o = _seed_opportunity(sig, opp)
    res = create_experiment(
        o["id"], experiment_type="manual_pilot", measurement_plan="notes",
        opportunities_root=opp, experiments_root=exp,
    )
    eid = res.experiment["id"]
    start_experiment(eid, opportunities_root=opp, experiments_root=exp)
    record_results(eid, qualitative_notes=["pilot done"], experiments_root=exp)
    complete_experiment(eid, experiments_root=exp, opportunities_root=opp)
    stored = list_experiments(exp)[eid]
    assert stored["status"] == "completed"
    assert "verdict" not in stored
