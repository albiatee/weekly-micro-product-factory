"""Phase 4 Experiment Engine — readiness, immutability, duplicate active."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.pipeline import ingest_manual_payload  # noqa: E402
from experiment.pipeline import (  # noqa: E402
    create_experiment,
    record_results,
    start_experiment,
    update_experiment_fields,
)
from experiment.readiness import is_experiment_ready  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402


def _seed(tmp_path: Path):
    sig, opp, exp = tmp_path / "s", tmp_path / "o", tmp_path / "e"
    for d in (sig, opp, exp):
        d.mkdir()
    r = ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": (
                "Shop owners struggle every week reconciling invoices manually "
                "and need a simple offline tool. [phase4-seed]"
            ),
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=sig,
    )
    sid = r.accepted[0]["signal"]["id"]
    g = generate_from_signal_ids([sid], signals_root=sig, opportunities_root=opp)
    assert g.accepted, g.rejected
    return sig, opp, exp, g.accepted[0]["opportunity"]


def _full_kwargs():
    return dict(
        experiment_type="waitlist",
        hypothesis_test="Target users will join a waitlist for an offline invoicing helper.",
        measurement_plan="Count qualified waitlist signups over 14 days",
        success_criteria={"metric": "qualified_signups", "min": 10, "window_days": 14},
        failure_criteria={"metric": "qualified_signups", "below": 3, "window_days": 14},
        target_population="Shop owners who reconcile invoices manually",
        duration="14d",
    )


def test_valid_create_and_start(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    res = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    assert res.ok, res.errors
    st = start_experiment(res.experiment["id"], opportunities_root=opp, experiments_root=exp)
    assert st.ok, st.errors
    assert st.experiment["status"] == "running"


def test_missing_opportunity(tmp_path):
    _, opp, exp, _ = _seed(tmp_path)
    res = create_experiment("opp_doesnotexist000", opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    assert not res.ok


def test_start_without_criteria_fails(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    # Bypass test defaults: build minimal planned experiment without criteria
    from experiment.build import build_experiment
    from experiment.store import upsert_experiment
    from experiment.readiness import is_experiment_ready

    bare = build_experiment(
        o,
        experiment_type="interview",
        hypothesis_test="Users will describe the invoicing pain in interviews clearly enough to refine the offer.",
        measurement_plan="Interview notes coded for problem confirmation",
        target_population="Shop owners",
    )
    # strip criteria if any
    bare.pop("success_criteria", None)
    bare.pop("failure_criteria", None)
    bare.pop("success_threshold", None)
    upsert_experiment(bare, exp)
    ok, errs = is_experiment_ready(bare, o)
    assert not ok
    st = start_experiment(bare["id"], opportunities_root=opp, experiments_root=exp)
    assert not st.ok
    assert any("success_criteria" in e or "failure_criteria" in e or "ready" in e for e in st.errors)


def test_invalid_type(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    res = create_experiment(
        o["id"],
        experiment_type="not_a_real_type",
        opportunities_root=opp,
        experiments_root=exp,
        **{k: v for k, v in _full_kwargs().items() if k != "experiment_type"},
    )
    assert not res.ok


def test_readiness_deterministic(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    res = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    a, ea = is_experiment_ready(res.experiment, o)
    b, eb = is_experiment_ready(res.experiment, o)
    assert a == b and ea == eb and a


def test_record_observations(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    res = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    assert start_experiment(res.experiment["id"], opportunities_root=opp, experiments_root=exp).ok
    rec = record_results(
        res.experiment["id"],
        metrics={"qualified_signups": 4},
        experiments_root=exp,
    )
    assert rec.ok
    assert rec.experiment["observations"]
    assert rec.experiment["observations"][0]["metric"] == "qualified_signups"


def test_immutable_after_results(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    res = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    eid = res.experiment["id"]
    assert start_experiment(eid, opportunities_root=opp, experiments_root=exp).ok
    assert record_results(eid, metrics={"qualified_signups": 1}, experiments_root=exp).ok
    bad = update_experiment_fields(
        eid, {"hypothesis_test": "Changed after seeing data"}, experiments_root=exp
    )
    assert not bad.ok
    assert any("cannot change" in e for e in bad.errors)


def test_duplicate_active_blocked(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    a = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    b = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    assert a.ok and b.ok
    assert start_experiment(a.experiment["id"], opportunities_root=opp, experiments_root=exp).ok
    second = start_experiment(b.experiment["id"], opportunities_root=opp, experiments_root=exp)
    assert not second.ok
    assert any("active running" in e for e in second.errors)


def test_traceability_to_opportunity(tmp_path):
    _, opp, exp, o = _seed(tmp_path)
    res = create_experiment(o["id"], opportunities_root=opp, experiments_root=exp, **_full_kwargs())
    assert res.experiment["opportunity_id"] == o["id"]
    assert o.get("signal_ids")
