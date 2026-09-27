"""P8 Closed Autonomous Loop — full path, gates, idempotency."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opportunity.store import upsert_opportunity, list_opportunities
from opportunity.evidence import is_evidence_ready
from orchestrator.closed_loop import run_closed_loop
from orchestrator.state_machine import can_transition, transition
from orchestrator.store import get_cycle, load_index
from production.automated_build import run_automated_build
from guardrails.checks import check_produce_path
from policy.evaluate import evaluate_decision
from policy.config import load_config


def test_state_machine_blocks_experimenting_to_building():
    assert not can_transition("experimenting", "building")
    ok, msg = transition("experimenting", "building")
    assert not ok
    assert "illegal" in msg


def _ready_opp(tmp: Path, oid: str = "opp_p8fullaaaaaaaa") -> str:
    opp = {
        "id": oid,
        "status": "hypothesized",
        "title": "P8 inventory micro tool",
        "problem": "Merchants lose sales when spreadsheets lag multi-channel inventory.",
        "audience": "small sellers",
        "created_by": "test",
        "created_at": "2026-09-20T00:00:00Z",
        "updated_at": "2026-09-20T00:00:00Z",
        "signal_ids": ["sig_p8fullaaaaaaaa"],
        "solution_type": "digital_micro",
        "evidence": [
            {
                "type": "signal_excerpt",
                "signal_id": "sig_p8fullaaaaaaaa",
                "summary": "Spreadsheets lag live inventory across channels causing stockouts.",
                "strength": "strong",
            }
        ],
        "assumptions": [],
        "unknowns": [],
    }
    assert is_evidence_ready(opp)[0]
    upsert_opportunity(opp, tmp / "opportunities")
    return oid


def _roots(tmp: Path) -> dict:
    return dict(
        signals_root=tmp / "signals",
        opportunities_root=tmp / "opportunities",
        experiments_root=tmp / "experiments",
        decisions_root=tmp / "decisions",
        cycles_root=tmp / "cycles",
        analytics_root=tmp / "analytics",
        builds_root=tmp / "builds",
        production_root=tmp / "production",
        products_dir=tmp / "bridge",
        templates_dir=ROOT / "templates",
        experiment_runs_root=tmp / "runs",
        config_path=ROOT / "config" / "orchestrator_v0.json",
    )


def test_full_success_path_isolated(tmp_path):
    """Signal/opportunity → experiment → execute → build → analytics → learning."""
    oid = _ready_opp(tmp_path)
    res = run_closed_loop(
        dry_run=False,
        force_enabled=True,
        opportunity_id=oid,
        metrics={"signups": 10},
        persist=True,
        **_roots(tmp_path),
    )
    assert res.ok, (res.errors, res.cycle.get("failure_reason"), res.cycle.get("step_log"))
    assert res.cycle["state"] == "completed"
    assert res.cycle["outcome"] == "execute_build_measured"
    assert res.cycle["live_publish"] is False
    assert res.cycle.get("experiment_ids")
    assert res.cycle.get("decision_ids")
    assert res.cycle.get("build_ids")
    assert res.cycle.get("analytics_ids")
    assert res.cycle.get("learning_ids")
    assert list((tmp_path / "bridge").rglob("index.html"))
    # Path A not written
    assert not (ROOT / "products" / "weekly" / "p8full").exists()


def test_idempotency_same_cycle_id(tmp_path):
    oid = _ready_opp(tmp_path, oid="opp_p8idemaaaaaaaa")
    roots = _roots(tmp_path)
    cid = "cyc_idempotencytest1"
    r1 = run_closed_loop(
        dry_run=False,
        force_enabled=True,
        opportunity_id=oid,
        metrics={"signups": 10},
        cycle_id=cid,
        persist=True,
        **roots,
    )
    assert r1.ok, r1.errors
    builds_after_1 = len(list((tmp_path / "bridge").rglob("index.html")))
    decisions_1 = len(json.loads((tmp_path / "decisions" / "index.json").read_text())["decisions"]) if (tmp_path / "decisions" / "index.json").exists() else 0

    r2 = run_closed_loop(
        dry_run=False,
        force_enabled=True,
        opportunity_id=oid,
        metrics={"signups": 10},
        cycle_id=cid,
        persist=True,
        **roots,
    )
    assert r2.cycle.get("idempotent_replay") is True
    assert r2.cycle["id"] == cid
    builds_after_2 = len(list((tmp_path / "bridge").rglob("index.html")))
    assert builds_after_2 == builds_after_1
    decisions_2 = len(json.loads((tmp_path / "decisions" / "index.json").read_text())["decisions"])
    assert decisions_2 == decisions_1


def test_kill_switch_blocks_live(tmp_path):
    oid = _ready_opp(tmp_path, oid="opp_p8killaaaaaaaa")
    res = run_closed_loop(
        dry_run=False,
        force_enabled=False,
        opportunity_id=oid,
        metrics={"signups": 10},
        persist=False,
        **_roots(tmp_path),
    )
    assert res.cycle.get("state") == "killed"
    assert not list((tmp_path / "bridge").rglob("index.html")) if (tmp_path / "bridge").exists() else True


def test_policy_kill_no_build(tmp_path):
    """Failure criteria met → kill → no build."""
    oid = _ready_opp(tmp_path, oid="opp_p8polkaaaaaaaaa")
    res = run_closed_loop(
        dry_run=False,
        force_enabled=True,
        opportunity_id=oid,
        metrics={"signups": 0},  # meets failure < 1
        persist=True,
        **_roots(tmp_path),
    )
    assert res.cycle.get("live_publish") is False
    # should not build
    assert not list((tmp_path / "bridge").rglob("*")) if (tmp_path / "bridge").exists() else True
    verdict = (res.cycle.get("refs") or {}).get("policy_verdict")
    assert verdict in ("kill", "iterate", "no_decision", "execute")
    if verdict == "kill":
        assert res.cycle.get("outcome") == "decision_kill"


def test_guardrail_blocks_non_execute_produce():
    cfg = load_config(ROOT / "config" / "orchestrator_v0.json")
    gr = check_produce_path(
        verdict="kill",
        dry_run=False,
        criteria_snapshot=True,
        metrics_snapshot={"signups": 10},
        build_template="static_html_microproduct",
        config=cfg,
    )
    assert not gr.ok
    assert any("verdict_not_execute" in b for b in gr.blocks)


def test_guardrail_blocks_bad_template():
    cfg = load_config(ROOT / "config" / "orchestrator_v0.json")
    gr = check_produce_path(
        verdict="execute",
        dry_run=False,
        criteria_snapshot=True,
        metrics_snapshot={"signups": 10},
        build_template="shopify_app",
        config=cfg,
    )
    assert not gr.ok
    assert any("template_not_allowed" in b for b in gr.blocks)


def test_build_requires_execute_decision(tmp_path):
    """P6 rejects non-execute even if called directly."""
    from decision.store import upsert_decision
    from experiment.store import upsert_experiment

    oid = _ready_opp(tmp_path, oid="opp_p8bypaaaaaaaa")
    # force building status without real execute path
    opp = list_opportunities(tmp_path / "opportunities")[oid]
    opp = {**opp, "status": "building", "latest_decision_id": "dec_fakekillaaaaaaaa"}
    upsert_opportunity(opp, tmp_path / "opportunities")
    upsert_experiment(
        {
            "id": "exp_fakekillaaaaaaaa",
            "opportunity_id": oid,
            "status": "completed",
            "experiment_type": "smoke_page",
            "hypothesis_test": "Users will signup if we show a minimal inventory lag smoke page.",
            "target_population": "sellers",
            "measurement_plan": {"metric": "signups"},
            "success_criteria": {"metric": "signups", "op": ">=", "value": 5},
            "failure_criteria": {"metric": "signups", "op": "<", "value": 1},
            "created_by": "test",
            "created_at": "2026-09-20T00:00:00Z",
            "updated_at": "2026-09-20T00:00:00Z",
            "results": {"metrics": {"signups": 0}},
        },
        tmp_path / "experiments",
    )
    upsert_decision(
        {
            "id": "dec_fakekillaaaaaaaa",
            "opportunity_id": oid,
            "experiment_id": "exp_fakekillaaaaaaaa",
            "verdict": "kill",
            "reason": "Failure criteria met deliberately for bypass test case here.",
            "evidence_refs": ["exp_fakekillaaaaaaaa"],
            "decided_by": "human",
            "created_at": "2026-09-20T00:00:00Z",
        },
        tmp_path / "decisions",
    )
    b = run_automated_build(
        "dec_fakekillaaaaaaaa",
        opportunities_root=tmp_path / "opportunities",
        decisions_root=tmp_path / "decisions",
        experiments_root=tmp_path / "experiments",
        production_root=tmp_path / "production",
        products_dir=tmp_path / "bridge",
        builds_root=tmp_path / "builds",
        templates_dir=ROOT / "templates",
    )
    assert not b.ok
    assert any("execute" in e for e in b.errors)


def test_dry_run_no_production_writes(tmp_path):
    oid = _ready_opp(tmp_path, oid="opp_p8dryaaaaaaaa")
    res = run_closed_loop(
        dry_run=True,
        force_enabled=True,
        opportunity_id=oid,
        metrics={"signups": 10},
        persist=False,
        **_roots(tmp_path),
    )
    assert res.cycle["dry_run"] is True
    assert res.cycle["live_publish"] is False
    assert not list((tmp_path / "bridge").rglob("index.html")) if (tmp_path / "bridge").exists() else True


def test_api_cycles_run_dry():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app

    c = TestClient(app)
    r = c.post("/cycles/run", json={"dry_run": True})
    assert r.status_code == 200
    assert r.json()["live_publish"] is False


def test_knowledge_similarity_not_rejection():
    from knowledge.search import compare_idea

    r = compare_idea("inventory spreadsheet lag", limit=2)
    assert r["decision"] is None
