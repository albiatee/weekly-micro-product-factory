"""Phase 7 — Distribution tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from distribution.pipeline import (  # noqa: E402
    cancel_plan,
    complete_plan,
    create_plan,
    record_action,
    record_result,
    start_plan,
)
from distribution.store import list_actions, list_plans  # noqa: E402
from distribution.validate import validate_plan_transition  # noqa: E402
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
    dist = tmp_path / "distribution"
    products = tmp_path / "products"
    templates = tmp_path / "templates" / "calculator"
    templates.mkdir(parents=True)
    (templates / "index.html").write_text("<html>ship</html>\n", encoding="utf-8")
    for d in (sig, opp, exp, dec, dist, products):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "sig": sig,
        "opp": opp,
        "exp": exp,
        "dec": dec,
        "dist": dist,
        "products": products,
        "templates": templates.parent,
    }


def _ship(env) -> str:
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_distribution-6]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=env["sig"],
    )
    sid = list(list_signals(env["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=env["sig"], opportunities_root=env["opp"]
    ).accepted[0]["opportunity"]["id"]
    o = list_opportunities(env["opp"])[oid]
    o["solution_type"] = "digital_micro"
    upsert_opportunity(o, env["opp"])
    er = _exp_pipe.create_experiment(
        oid, experiment_type="waitlist", measurement_plan="m",
        opportunities_root=env["opp"], experiments_root=env["exp"],
    )
    eid = er.experiment["id"]
    start_experiment(eid, opportunities_root=env["opp"], experiments_root=env["exp"])
    record_results(eid, metrics={"n": 1}, experiments_root=env["exp"])
    complete_experiment(eid, experiments_root=env["exp"], opportunities_root=env["opp"])
    assert create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason="Execute after completed experiment met predefined success path for shipping",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=env["opp"],
        experiments_root=env["exp"],
        signals_root=env["sig"],
        decisions_root=env["dec"],
    ).ok
    br = run_production_bridge(
        oid,
        opportunities_root=env["opp"],
        decisions_root=env["dec"],
        templates_dir=env["templates"],
        products_dir=env["products"],
    )
    assert br.ok, br.errors
    assert list_opportunities(env["opp"])[oid]["status"] == "shipped"
    return oid


def test_shipped_allows_distribution(env):
    oid = _ship(env)
    res = create_plan(
        oid,
        channel="telegram",
        objective="Announce shipped micro tool",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
    )
    assert res.ok, res.errors
    assert res.plan["id"].startswith("dist_")
    assert res.plan["status"] == "planned"


def test_building_rejected(env):
    # opportunity hypothesized only
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Shop owners struggle every week because they waste hours reconciling invoices manually without a simple offline tool. [test_distribution-7]",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=env["sig"],
    )
    sid = list(list_signals(env["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=env["sig"], opportunities_root=env["opp"]
    ).accepted[0]["opportunity"]["id"]
    res = create_plan(
        oid,
        channel="github",
        objective="nope",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
        require_artifact=False,
    )
    assert not res.ok


def test_invalid_channel(env):
    oid = _ship(env)
    res = create_plan(
        oid,
        channel="tiktok",
        objective="x",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
    )
    assert not res.ok


def test_lifecycle_and_actions(env):
    oid = _ship(env)
    plan = create_plan(
        oid,
        channel="community",
        objective="Share with community",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
    ).plan
    pid = plan["id"]
    assert start_plan(pid, distribution_root=env["dist"]).ok
    act = record_action(
        pid, action_type="manual_post", notes="Posted once", distribution_root=env["dist"]
    )
    assert act.ok, act.errors
    assert act.action["id"].startswith("dact_")
    # duplicate
    assert not record_action(
        pid, action_type="manual_post", notes="Posted once", distribution_root=env["dist"]
    ).ok
    assert record_result(
        pid, metrics={"clicks": 3}, qualitative_notes=["ok"], distribution_root=env["dist"]
    ).ok
    assert complete_plan(pid, distribution_root=env["dist"]).ok
    assert list_plans(env["dist"])[pid]["status"] == "completed"
    assert not validate_plan_transition("completed", "running").ok


def test_duplicate_plan_same_channel(env):
    oid = _ship(env)
    assert create_plan(
        oid,
        channel="x",
        objective="one",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
    ).ok
    assert not create_plan(
        oid,
        channel="x",
        objective="two",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
    ).ok


def test_dry_run_no_persist(env):
    oid = _ship(env)
    res = create_plan(
        oid,
        channel="direct",
        objective="dry",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
        dry_run=True,
    )
    assert res.ok
    assert list_plans(env["dist"]) == {}


def test_cancel_terminal(env):
    oid = _ship(env)
    pid = create_plan(
        oid,
        channel="seo",
        objective="later",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
    ).plan["id"]
    assert cancel_plan(pid, distribution_root=env["dist"]).ok
    assert not start_plan(pid, distribution_root=env["dist"]).ok


def test_missing_artifact_rejected(env):
    oid = _ship(env)
    # wipe product files
    for p in env["products"].iterdir():
        import shutil

        shutil.rmtree(p)
    res = create_plan(
        oid,
        channel="telegram",
        objective="no artifact",
        opportunities_root=env["opp"],
        distribution_root=env["dist"],
        products_root=env["products"],
        require_artifact=True,
    )
    assert not res.ok
