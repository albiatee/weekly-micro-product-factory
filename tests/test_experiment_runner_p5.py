"""P5 Experiment Runner tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment.runner import run_experiment, complete_with_metrics
from opportunity.store import upsert_opportunity
from opportunity.evidence import is_evidence_ready


def _evidence_ready_opp(tmp: Path, oid: str = "opp_testaaaaaaaaaa") -> dict:
    opp = {
        "id": oid,
        "status": "hypothesized",
        "title": "Inventory spreadsheet multi-channel stockouts",
        "problem": "Merchants lose sales when spreadsheets lag multi-channel inventory updates daily.",
        "audience": "small ecommerce sellers",
        "created_by": "test",
        "created_at": "2026-09-20T00:00:00Z",
        "updated_at": "2026-09-20T00:00:00Z",
        "signal_ids": ["sig_testaaaaaaaaaa"],
        "evidence": [
            {
                "type": "signal_excerpt",
                "signal_id": "sig_testaaaaaaaaaa",
                "summary": "Spreadsheets lag live inventory across Shopify and Amazon causing stockouts.",
                "strength": "strong",
            }
        ],
        "assumptions": [{"assumption": "untested", "status": "untested"}],
        "unknowns": ["willingness to pay"],
    }
    assert is_evidence_ready(opp)[0]
    upsert_opportunity(opp, tmp / "opportunities")
    return opp


def test_dry_run_plans_only(tmp_path):
    opp = _evidence_ready_opp(tmp_path)
    res = run_experiment(
        opp["id"],
        dry_run=True,
        opportunities_root=tmp_path / "opportunities",
        experiments_root=tmp_path / "experiments",
        runs_root=tmp_path / "runs",
    )
    assert res.ok
    assert res.experiment["status"] == "planned"
    assert res.artifact_path is None


def test_run_without_metrics_stays_running(tmp_path):
    opp = _evidence_ready_opp(tmp_path)
    res = run_experiment(
        opp["id"],
        experiment_type="smoke_page",
        opportunities_root=tmp_path / "opportunities",
        experiments_root=tmp_path / "experiments",
        runs_root=tmp_path / "runs",
    )
    assert res.ok
    assert res.experiment["status"] == "running"
    assert res.artifact_path and Path(res.artifact_path).exists()
    assert (Path(res.run_dir) / "index.html").exists()


def test_run_with_metrics_completes_and_policy(tmp_path):
    opp = _evidence_ready_opp(tmp_path)
    res = run_experiment(
        opp["id"],
        metrics={"signups": 7},
        success_criteria={"metric": "signups", "op": ">=", "value": 5},
        failure_criteria={"metric": "signups", "op": "<", "value": 1},
        opportunities_root=tmp_path / "opportunities",
        experiments_root=tmp_path / "experiments",
        runs_root=tmp_path / "runs",
    )
    assert res.ok, res.errors
    assert res.experiment["status"] == "completed"
    assert res.metrics["signups"] == 7
    assert res.policy is not None
    assert res.policy["advisory"] is True
    assert res.policy["verdict"] in ("execute", "iterate", "kill", "no_decision")


def test_disallowed_type(tmp_path):
    opp = _evidence_ready_opp(tmp_path)
    res = run_experiment(
        opp["id"],
        experiment_type="preorder",
        opportunities_root=tmp_path / "opportunities",
        experiments_root=tmp_path / "experiments",
        runs_root=tmp_path / "runs",
    )
    assert not res.ok


def test_complete_with_metrics(tmp_path):
    opp = _evidence_ready_opp(tmp_path)
    res = run_experiment(
        opp["id"],
        opportunities_root=tmp_path / "opportunities",
        experiments_root=tmp_path / "experiments",
        runs_root=tmp_path / "runs",
    )
    assert res.experiment["status"] == "running"
    done = complete_with_metrics(
        res.experiment["id"],
        {"signups": 0},
        opportunities_root=tmp_path / "opportunities",
        experiments_root=tmp_path / "experiments",
        runs_root=tmp_path / "runs",
    )
    assert done.ok
    assert done.experiment["status"] == "completed"


def test_api_experiments_run():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app

    c = TestClient(app)
    # dry-run against real store may fail if no evidence-ready opp; just ensure endpoint exists
    r = c.post(
        "/experiments/run",
        json={"opportunity_id": "opp_nonexistent", "dry_run": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["live_publish"] is False
    assert body["ok"] is False
