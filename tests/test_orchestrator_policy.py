"""Control plane: policy, select, steps, dry-run."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestrator.steps import is_jump, steps_until, STEPS
from orchestrator.kill_switch import is_enabled
from orchestrator.runner import run_cycle
from policy.evaluate import evaluate_decision
from policy.select import select_opportunities, score_opportunity
from policy.config import load_config
from guardrails.checks import check_produce_path, check_publish


def test_steps_no_jump():
    assert is_jump(None, "QUALIFY") is True
    assert is_jump(None, "COLLECT") is False
    assert is_jump("SELECT", "BUILD") is True
    assert is_jump("SELECT", "EXPERIMENT") is False
    assert steps_until("SELECT") == STEPS[:4]


def test_kill_switch_default_off():
    cfg = load_config()
    assert is_enabled(cfg, env={}) is False
    assert is_enabled(cfg, env={"ORCHESTRATOR_ENABLED": "true"}) is True


def test_policy_no_decision_unless_completed():
    r = evaluate_decision(experiment={"status": "running", "id": "exp_x"})
    assert r.verdict == "no_decision"


def test_policy_execute_structured_success():
    exp = {
        "id": "exp_x",
        "status": "completed",
        "success_criteria": {"metric": "signups", "op": ">=", "value": 10},
        "failure_criteria": {"metric": "signups", "op": "<", "value": 3},
        "results": {"metrics": {"signups": 12}},
    }
    cfg = load_config()
    r = evaluate_decision(experiment=exp, config=cfg)
    assert r.verdict == "execute"
    assert "success_criteria_met" in r.rule_hits


def test_policy_kill_on_failure():
    exp = {
        "id": "exp_x",
        "status": "completed",
        "success_criteria": {"metric": "signups", "op": ">=", "value": 10},
        "failure_criteria": {"metric": "signups", "op": "<", "value": 3},
        "results": {"metrics": {"signups": 1}},
    }
    r = evaluate_decision(experiment=exp, config=load_config())
    assert r.verdict == "kill"


def test_policy_iterate_grey_zone():
    exp = {
        "id": "exp_x",
        "status": "completed",
        "success_criteria": "at least 10 signups (prose)",
        "failure_criteria": "fewer than 3",
        "results": {"metrics": {"signups": 5}},
    }
    r = evaluate_decision(experiment=exp, config=load_config(), iteration_count=0)
    assert r.verdict == "iterate"


def test_select_deterministic(tmp_path):
    cfg = load_config()
    opps = [
        {
            "id": "opp_b",
            "status": "hypothesized",
            "problem": "x" * 30,
            "audience": "sellers",
            "signal_ids": ["sig_aaaaaaaaaaaaaaaa"],
            "evidence": [
                {
                    "type": "signal_excerpt",
                    "signal_id": "sig_aaaaaaaaaaaaaaaa",
                    "summary": "inventory spreadsheets break at volume",
                    "strength": "strong",
                }
            ],
            "assumptions": [],
            "unknowns": [],
        },
        {
            "id": "opp_a",
            "status": "hypothesized",
            "problem": "y" * 30,
            "audience": "shops",
            "signal_ids": ["sig_bbbbbbbbbbbbbbbb"],
            "evidence": [
                {
                    "type": "signal_excerpt",
                    "signal_id": "sig_bbbbbbbbbbbbbbbb",
                    "summary": "weaker evidence note",
                    "strength": "weak",
                }
            ],
            "assumptions": [],
            "unknowns": [],
        },
    ]
    selected = select_opportunities(opps, config=cfg)
    assert len(selected) == 1
    assert selected[0]["id"] == "opp_b"  # higher strength rank


def test_guardrails_block_dry_run():
    gr = check_produce_path(
        verdict="execute",
        dry_run=True,
        criteria_snapshot={"ok": True},
        metrics_snapshot={"signups": 1},
        build_template="static_html_microproduct",
        config=load_config(),
    )
    assert gr.ok is False
    assert "dry_run" in gr.blocks


def test_dry_run_cycle_completes(tmp_path):
    roots = {n: tmp_path / n for n in ("sig", "opp", "exp", "dec", "cyc")}
    for r in roots.values():
        r.mkdir()
    # minimal signal for qualify path
    from discovery.pipeline import ingest_manual_payload

    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": (
                "Shop owners struggle every week reconciling multi-channel inventory "
                "in spreadsheets causing stockouts and overselling."
            ),
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=roots["sig"],
    )
    cycle = run_cycle(
        dry_run=True,
        stop_after="SELECT",
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        cycles_root=roots["cyc"],
        force_enabled=True,
        persist=True,
    )
    assert cycle["status"] == "completed"
    assert "SELECT" in cycle["completed_steps"]
    assert cycle["dry_run"] is True
