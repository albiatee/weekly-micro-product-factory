"""P6 Automated Build tests — execute only, no publish, fail-safe."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from decision.store import upsert_decision
from experiment.store import upsert_experiment
from opportunity.store import upsert_opportunity
from production.automated_build import run_automated_build


def _chain(tmp: Path, *, verdict: str = "execute", opp_status: str = "building"):
    oid, eid, did = "opp_buildtestaaaaaa", "exp_buildtestaaaaaa", "dec_buildtestaaaaaa"
    opp = {
        "id": oid,
        "status": opp_status,
        "title": "Inventory lag tool",
        "problem": "Merchants need a simple offline micro tool for inventory lag awareness.",
        "audience": "small sellers",
        "created_by": "test",
        "created_at": "2026-09-20T00:00:00Z",
        "updated_at": "2026-09-20T00:00:00Z",
        "signal_ids": ["sig_buildtestaaaaaa"],
        "solution_type": "digital_micro",
        "evidence": [
            {
                "type": "signal_excerpt",
                "signal_id": "sig_buildtestaaaaaa",
                "summary": "Inventory spreadsheets lag multi-channel sales.",
                "strength": "strong",
            }
        ],
        "assumptions": [],
        "unknowns": [],
        "latest_decision_id": did,
        "active_experiment_id": eid,
    }
    exp = {
        "id": eid,
        "opportunity_id": oid,
        "status": "completed",
        "experiment_type": "smoke_page",
        "hypothesis_test": "Users will signup if we show a minimal inventory lag smoke page.",
        "target_population": "small sellers",
        "measurement_plan": {"metric": "signups"},
        "success_criteria": {"metric": "signups", "op": ">=", "value": 5},
        "failure_criteria": {"metric": "signups", "op": "<", "value": 1},
        "created_by": "test",
        "created_at": "2026-09-20T00:00:00Z",
        "updated_at": "2026-09-20T00:00:00Z",
        "results": {"metrics": {"signups": 7}},
    }
    dec = {
        "id": did,
        "opportunity_id": oid,
        "experiment_id": eid,
        "verdict": verdict,
        "reason": "Success criteria met in completed experiment with metrics.",
        "evidence_refs": [eid],
        "decided_by": "human",
        "created_at": "2026-09-20T00:00:00Z",
        "criteria_snapshot": exp["success_criteria"],
        "metrics_snapshot": {"signups": 7},
    }
    upsert_opportunity(opp, tmp / "opportunities")
    upsert_experiment(exp, tmp / "experiments")
    upsert_decision(dec, tmp / "decisions")
    return oid, eid, did


def test_reject_non_execute(tmp_path):
    _, _, did = _chain(tmp_path, verdict="kill")
    res = run_automated_build(
        did,
        opportunities_root=tmp_path / "opportunities",
        decisions_root=tmp_path / "decisions",
        experiments_root=tmp_path / "experiments",
        production_root=tmp_path / "production",
        products_dir=tmp_path / "bridge_out",
        builds_root=tmp_path / "builds",
        templates_dir=ROOT / "templates",
    )
    assert not res.ok
    assert any("execute" in e for e in res.errors)


def test_reject_wrong_status(tmp_path):
    _, _, did = _chain(tmp_path, opp_status="hypothesized")
    res = run_automated_build(
        did,
        opportunities_root=tmp_path / "opportunities",
        decisions_root=tmp_path / "decisions",
        experiments_root=tmp_path / "experiments",
        production_root=tmp_path / "production",
        products_dir=tmp_path / "bridge_out",
        builds_root=tmp_path / "builds",
        templates_dir=ROOT / "templates",
    )
    assert not res.ok


def test_dry_run_no_artifact(tmp_path):
    _, _, did = _chain(tmp_path)
    res = run_automated_build(
        did,
        dry_run=True,
        opportunities_root=tmp_path / "opportunities",
        decisions_root=tmp_path / "decisions",
        experiments_root=tmp_path / "experiments",
        production_root=tmp_path / "production",
        products_dir=tmp_path / "bridge_out",
        builds_root=tmp_path / "builds",
        templates_dir=ROOT / "templates",
    )
    assert res.ok
    assert res.dry_run is True
    assert not (tmp_path / "bridge_out").exists() or not any((tmp_path / "bridge_out").iterdir())


def test_build_success_traceable(tmp_path):
    oid, _, did = _chain(tmp_path)
    res = run_automated_build(
        did,
        opportunities_root=tmp_path / "opportunities",
        decisions_root=tmp_path / "decisions",
        experiments_root=tmp_path / "experiments",
        production_root=tmp_path / "production",
        products_dir=tmp_path / "bridge_out",
        builds_root=tmp_path / "builds",
        templates_dir=ROOT / "templates",
    )
    assert res.ok, res.errors
    assert res.build_id and res.build_id.startswith("bld_")
    assert res.production_spec_id
    assert res.artifact_path
    # artifact exists
    seg = oid  # safe segment may transform
    out = tmp_path / "bridge_out"
    assert out.exists()
    found = list(out.rglob("index.html"))
    assert found, "expected index.html artifact"
    meta = found[0].parent / "meta.json"
    assert meta.exists()
    # build log
    log = json.loads((tmp_path / "builds" / "index.json").read_text())
    assert res.build_id in log["builds"]
    assert log["builds"][res.build_id]["status"] == "succeeded"
    # Path A weekly untouched
    assert not (ROOT / "products" / "weekly" / "bridge_test").exists()


def test_duplicate_target_fail_safe(tmp_path):
    oid, _, did = _chain(tmp_path)
    kwargs = dict(
        opportunities_root=tmp_path / "opportunities",
        decisions_root=tmp_path / "decisions",
        experiments_root=tmp_path / "experiments",
        production_root=tmp_path / "production",
        products_dir=tmp_path / "bridge_out",
        builds_root=tmp_path / "builds",
        templates_dir=ROOT / "templates",
    )
    r1 = run_automated_build(did, **kwargs)
    assert r1.ok
    # second build should fail (target exists) without corrupting first
    r2 = run_automated_build(did, **kwargs)
    assert not r2.ok
    found = list((tmp_path / "bridge_out").rglob("index.html"))
    assert len(found) >= 1


def test_api_build_endpoint():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app

    c = TestClient(app)
    r = c.post("/builds/run", json={"decision_id": "dec_nonexistent", "dry_run": True})
    assert r.status_code == 200
    body = r.json()
    assert body["live_publish"] is False
    assert body["ok"] is False
