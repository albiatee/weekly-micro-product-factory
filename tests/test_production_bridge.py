"""Phase 6 — Production Bridge tests (isolated roots; no weekly-build)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from decision.pipeline import create_decision  # noqa: E402
from decision.store import list_decisions  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from experiment.pipeline import (  # noqa: E402
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities, upsert_opportunity  # noqa: E402
from production.bridge import run_production_bridge  # noqa: E402


@pytest.fixture
def env(tmp_path: Path):
    sig = tmp_path / "signals"
    opp = tmp_path / "opportunities"
    exp = tmp_path / "experiments"
    dec = tmp_path / "decisions"
    products = tmp_path / "products_bridge"
    templates = tmp_path / "templates" / "calculator"
    templates.mkdir(parents=True)
    (templates / "index.html").write_text(
        "<!DOCTYPE html><html><body>bridge-test</body></html>\n", encoding="utf-8"
    )
    for d in (sig, opp, exp, dec, products):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "sig": sig,
        "opp": opp,
        "exp": exp,
        "dec": dec,
        "products": products,
        "templates": templates.parent,
    }


def _to_building(env, solution_type: str = "digital_micro"):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_production_bridge-3]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=env["sig"],
    )
    sid = list(list_signals(env["sig"]).keys())[0]
    g = generate_from_signal_ids(
        [sid], signals_root=env["sig"], opportunities_root=env["opp"]
    )
    oid = g.accepted[0]["opportunity"]["id"]
    # force solution_type for gate tests
    o = list_opportunities(env["opp"])[oid]
    o["solution_type"] = solution_type
    upsert_opportunity(o, env["opp"])

    er = _exp_pipe.create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="signups",
        opportunities_root=env["opp"],
        experiments_root=env["exp"],
    )
    eid = er.experiment["id"]
    start_experiment(eid, opportunities_root=env["opp"], experiments_root=env["exp"])
    record_results(eid, metrics={"signups": 3}, experiments_root=env["exp"])
    complete_experiment(eid, experiments_root=env["exp"], opportunities_root=env["opp"])
    dres = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="Completed experiment; explicit execute",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=env["opp"],
        experiments_root=env["exp"],
        signals_root=env["sig"],
        decisions_root=env["dec"],
    )
    assert dres.ok, dres.errors
    assert dres.opportunity["status"] == "building"
    return oid, eid, dres.decision["id"]


def test_execute_building_to_shipped(env):
    oid, eid, did = _to_building(env)
    res = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert res.ok, res.errors
    assert res.opportunity["status"] == "shipped"
    assert res.production_ref["decision_id"] == did
    assert res.production_ref["path"].startswith("products/bridge/")
    target = env["products"] / oid.replace("/", "-")  # safe segment keeps opp_ id mostly
    # path uses opportunity_id segment
    found = list(env["products"].iterdir())
    assert found
    assert (found[0] / "index.html").is_file()
    assert (found[0] / "meta.json").is_file()


def test_no_decision_rejected(env):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_production_bridge-4]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=env["sig"],
    )
    sid = list(list_signals(env["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=env["sig"], opportunities_root=env["opp"]
    ).accepted[0]["opportunity"]["id"]
    o = list_opportunities(env["opp"])[oid]
    o["status"] = "building"
    o["solution_type"] = "digital_micro"
    upsert_opportunity(o, env["opp"])
    res = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert not res.ok


def test_iterate_verdict_cannot_build(env):
    oid, eid, _ = _to_building(env)
    # Replace decision with iterate path by resetting — use kill/iterate opp
    # Simpler: force decision verdict iterate on store is hard; use wrong status path
    # Build second opp with iterate
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_production_bridge-5]",
            "captured_at": "2026-09-20T15:00:00Z",
        },
        store_root=env["sig"],
    )
    sid = list(list_signals(env["sig"]).keys())[-1]
    oid2 = generate_from_signal_ids(
        [sid], signals_root=env["sig"], opportunities_root=env["opp"]
    ).accepted[0]["opportunity"]["id"]
    o = list_opportunities(env["opp"])[oid2]
    o["solution_type"] = "digital_micro"
    upsert_opportunity(o, env["opp"])
    er = _exp_pipe.create_experiment(
        oid2, experiment_type="waitlist", measurement_plan="m",
        opportunities_root=env["opp"], experiments_root=env["exp"],
    )
    eid2 = er.experiment["id"]
    start_experiment(eid2, opportunities_root=env["opp"], experiments_root=env["exp"])
    record_results(eid2, metrics={"x": 1}, experiments_root=env["exp"])
    complete_experiment(eid2, experiments_root=env["exp"], opportunities_root=env["opp"])
    dres = create_decision(
        opportunity_id=oid2,
        verdict="iterate",
        reason="Iterate: need more tests before production; evidence is mixed",
        evidence_refs=[eid2],
        decided_by="human",
        experiment_id=eid2,
        opportunities_root=env["opp"],
        experiments_root=env["exp"],
        signals_root=env["sig"],
        decisions_root=env["dec"],
    )
    assert dres.ok
    assert dres.opportunity["status"] == "iterating"
    res = run_production_bridge(
        oid2,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert not res.ok


def test_unsupported_solution_type(env):
    oid, _, _ = _to_building(env, solution_type="saas")
    res = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert not res.ok
    assert any("solution_type" in e for e in res.errors)


def test_duplicate_production_ref_refused(env):
    oid, _, _ = _to_building(env)
    r1 = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert r1.ok
    r2 = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert not r2.ok


def test_dry_run_no_files(env):
    oid, _, _ = _to_building(env)
    res = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
        dry_run=True,
    )
    assert res.ok
    assert res.dry_run
    assert list(env["products"].iterdir()) == []
    assert list_opportunities(env["opp"])[oid]["status"] == "building"


def test_does_not_touch_repo_catalog(env, tmp_path):
    """Ensure bridge products_dir is isolated; catalog path unused."""
    oid, _, _ = _to_building(env)
    catalog = tmp_path / "catalog_index.json"
    catalog.write_text(json.dumps({"products": [{"keep": True}]}), encoding="utf-8")
    before = catalog.read_text(encoding="utf-8")
    run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert catalog.read_text(encoding="utf-8") == before
