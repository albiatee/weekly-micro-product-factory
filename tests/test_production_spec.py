"""Phase 6 — Production Specification (entry gate, no deploy)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from experiment.pipeline import complete_experiment, record_results, start_experiment  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities, upsert_opportunity  # noqa: E402
from production.pipeline import create_production_spec  # noqa: E402
from production.spec import is_production_ready  # noqa: E402
from production.store import list_production_specs  # noqa: E402


def _chain(tmp_path: Path, verdict: str = "execute"):
    sig = tmp_path / "sig"
    opp = tmp_path / "opp"
    exp = tmp_path / "exp"
    dec = tmp_path / "dec"
    prd = tmp_path / "prd"
    for d in (sig, opp, exp, dec, prd):
        d.mkdir()
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": (
                "Shop owners struggle every week reconciling invoices manually "
                "without a simple offline tool. [phase6-spec]"
            ),
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=sig,
    )
    sid = list(list_signals(sig).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=sig, opportunities_root=opp
    ).accepted[0]["opportunity"]["id"]
    o = list_opportunities(opp)[oid]
    o["solution_type"] = "digital_micro"
    upsert_opportunity(o, opp)

    er = _exp_pipe.create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count qualified signups over 14 days",
        opportunities_root=opp,
        experiments_root=exp,
    )
    eid = er.experiment["id"]
    assert start_experiment(eid, opportunities_root=opp, experiments_root=exp).ok
    assert record_results(eid, metrics={"signups": 12}, experiments_root=exp).ok
    assert complete_experiment(eid, experiments_root=exp, opportunities_root=opp).ok

    dres = create_decision(
        opportunity_id=oid,
        verdict=verdict,
        reason="Predefined success path met with recorded signups; authorize production planning only.",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=opp,
        experiments_root=exp,
        signals_root=sig,
        decisions_root=dec,
    )
    return {
        "sig": sig,
        "opp": opp,
        "exp": exp,
        "dec": dec,
        "prd": prd,
        "oid": oid,
        "eid": eid,
        "dres": dres,
    }


def test_execute_creates_spec(tmp_path):
    c = _chain(tmp_path, "execute")
    assert c["dres"].ok, c["dres"].errors
    res = create_production_spec(
        decision_id=c["dres"].decision["id"],
        opportunities_root=c["opp"],
        decisions_root=c["dec"],
        experiments_root=c["exp"],
        production_root=c["prd"],
    )
    assert res.ok, res.errors
    spec = res.production_spec
    assert spec["id"].startswith("prd_")
    assert spec["decision_id"] == c["dres"].decision["id"]
    assert spec["opportunity_id"] == c["oid"]
    assert spec["experiment_id"] == c["eid"]
    assert spec["source_signal_ids"]
    assert spec["criteria_snapshot"]
    assert spec["metrics_snapshot"]
    assert spec["production_status"] == "ready"
    assert spec["core_features"]
    assert spec["non_goals"]
    assert spec["acceptance_criteria"]
    assert "assumptions" in spec


def test_iterate_rejected(tmp_path):
    c = _chain(tmp_path, "iterate")
    assert c["dres"].ok
    res = create_production_spec(
        decision_id=c["dres"].decision["id"],
        opportunities_root=c["opp"],
        decisions_root=c["dec"],
        experiments_root=c["exp"],
        production_root=c["prd"],
    )
    assert not res.ok
    assert any("execute" in e for e in res.errors)


def test_kill_rejected(tmp_path):
    c = _chain(tmp_path, "kill")
    assert c["dres"].ok
    res = create_production_spec(
        decision_id=c["dres"].decision["id"],
        opportunities_root=c["opp"],
        decisions_root=c["dec"],
        experiments_root=c["exp"],
        production_root=c["prd"],
    )
    assert not res.ok


def test_missing_decision(tmp_path):
    res = create_production_spec(
        decision_id="dec_doesnotexist0000",
        production_root=tmp_path / "prd",
    )
    assert not res.ok


def test_duplicate_spec_rejected(tmp_path):
    c = _chain(tmp_path, "execute")
    r1 = create_production_spec(
        decision_id=c["dres"].decision["id"],
        opportunities_root=c["opp"],
        decisions_root=c["dec"],
        experiments_root=c["exp"],
        production_root=c["prd"],
    )
    assert r1.ok
    r2 = create_production_spec(
        decision_id=c["dres"].decision["id"],
        opportunities_root=c["opp"],
        decisions_root=c["dec"],
        experiments_root=c["exp"],
        production_root=c["prd"],
    )
    assert not r2.ok


def test_dry_run_no_persist(tmp_path):
    c = _chain(tmp_path, "execute")
    res = create_production_spec(
        decision_id=c["dres"].decision["id"],
        opportunities_root=c["opp"],
        decisions_root=c["dec"],
        experiments_root=c["exp"],
        production_root=c["prd"],
        dry_run=True,
    )
    assert res.ok
    assert list_production_specs(c["prd"]) == {}


def test_gate_function():
    ok, errs = is_production_ready(
        {"verdict": "iterate", "opportunity_id": "opp_x", "experiment_id": "exp_x"},
        {"id": "opp_x", "status": "building"},
        {"id": "exp_x", "status": "completed", "opportunity_id": "opp_x"},
    )
    assert not ok
