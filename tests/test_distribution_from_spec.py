"""Phase 7 — Distribution from Production Specification."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import experiment.pipeline as _exp_pipe  # noqa: E402

from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from distribution.from_spec import (  # noqa: E402
    create_distribution_from_spec,
    prepare_distribution,
    record_publication,
)
from experiment.pipeline import complete_experiment, record_results, start_experiment  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities, upsert_opportunity  # noqa: E402
from production.pipeline import create_production_spec  # noqa: E402


def _full_chain(tmp_path: Path, verdict: str = "execute"):
    roots = {k: tmp_path / k for k in ("sig", "opp", "exp", "dec", "prd", "dist")}
    for d in roots.values():
        d.mkdir()
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": (
                "Shop owners struggle every week reconciling invoices manually "
                "without a simple offline tool. [phase7-dist]"
            ),
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    sid = list(list_signals(roots["sig"]).keys())[0]
    oid = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    ).accepted[0]["opportunity"]["id"]
    o = list_opportunities(roots["opp"])[oid]
    o["solution_type"] = "digital_micro"
    upsert_opportunity(o, roots["opp"])
    er = _exp_pipe.create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan="Count signups",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    eid = er.experiment["id"]
    assert start_experiment(eid, opportunities_root=roots["opp"], experiments_root=roots["exp"]).ok
    assert record_results(eid, metrics={"signups": 10}, experiments_root=roots["exp"]).ok
    assert complete_experiment(eid, experiments_root=roots["exp"], opportunities_root=roots["opp"]).ok
    dres = create_decision(
        opportunity_id=oid,
        verdict=verdict,
        reason="Authorize production planning from completed experiment evidence and criteria.",
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    assert dres.ok, dres.errors
    if verdict != "execute":
        return roots, None, dres
    sres = create_production_spec(
        decision_id=dres.decision["id"],
        opportunities_root=roots["opp"],
        decisions_root=roots["dec"],
        experiments_root=roots["exp"],
        production_root=roots["prd"],
    )
    assert sres.ok, sres.errors
    return roots, sres.production_spec, dres


def test_valid_spec_creates_planned_distribution(tmp_path):
    roots, spec, _ = _full_chain(tmp_path)
    res = create_distribution_from_spec(
        spec["id"],
        channel="landing_page",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert res["ok"], res["errors"]
    plan = res["plan"]
    assert plan["status"] == "planned"
    assert plan["publication"] is None
    assert plan["production_spec_id"] == spec["id"]
    assert plan["source_signal_ids"]
    assert plan["decision_id"]
    assert plan["experiment_id"]


def test_missing_spec_rejected(tmp_path):
    res = create_distribution_from_spec(
        "prd_missing00000000",
        channel="own_site",
        production_root=tmp_path / "empty",
        distribution_root=tmp_path / "d",
    )
    (tmp_path / "empty").mkdir(exist_ok=True)
    (tmp_path / "d").mkdir(exist_ok=True)
    assert not res["ok"]


def test_iterate_cannot_distribute(tmp_path):
    roots, _, dres = _full_chain(tmp_path, verdict="iterate")
    # no production spec for iterate — simulate wrong path
    res = create_distribution_from_spec(
        "prd_fake",
        channel="email",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert not res["ok"]


def test_kill_cannot_create_spec_path(tmp_path):
    roots, _, dres = _full_chain(tmp_path, verdict="kill")
    assert dres.decision["verdict"] == "kill"
    # Cannot get production spec; distribution from fake id fails
    res = create_distribution_from_spec(
        "prd_x",
        channel="social_post",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert not res["ok"]


def test_prepare_vs_published(tmp_path):
    roots, spec, _ = _full_chain(tmp_path)
    res = create_distribution_from_spec(
        spec["id"],
        channel="community_post",
        message="Draft post text",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert res["ok"]
    pid = res["plan"]["id"]
    prep = prepare_distribution(pid, distribution_root=roots["dist"])
    assert prep["ok"]
    assert prep["plan"]["status"] == "prepared"
    assert prep["plan"]["status"] != "published"
    pub = record_publication(
        pid, success=True, destination_url="https://example.invalid/x", distribution_root=roots["dist"]
    )
    assert pub["ok"]
    assert pub["plan"]["status"] == "published"
    assert pub["plan"]["publication"]["source"] == "manual_operator_report"


def test_duplicate_channel_rejected(tmp_path):
    roots, spec, _ = _full_chain(tmp_path)
    kw = dict(
        channel="product_catalog",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert create_distribution_from_spec(spec["id"], **kw)["ok"]
    r2 = create_distribution_from_spec(spec["id"], **kw)
    assert not r2["ok"]


def test_invalid_channel(tmp_path):
    roots, spec, _ = _full_chain(tmp_path)
    res = create_distribution_from_spec(
        spec["id"],
        channel="tiktok_ads_paid",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert not res["ok"]
