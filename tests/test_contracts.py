"""Phase 1 — Schema Contract validation tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.validate import (  # noqa: E402
    validate_decision,
    validate_experiment,
    validate_graph,
    validate_learning_record,
    validate_opportunity,
    validate_opportunity_transition,
    validate_signal,
)


def test_signal_valid_minimal():
    r = validate_signal(
        {
            "id": "sig_1",
            "source": "other",
            "raw_text": "pain point",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    )
    assert r.ok, r.errors


def test_signal_invalid_source():
    r = validate_signal(
        {
            "id": "sig_1",
            "source": "telegram",
            "raw_text": "x",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok


def test_signal_bad_prefix():
    r = validate_signal(
        {
            "id": "x_1",
            "source": "manual",
            "raw_text": "x",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok


def test_opportunity_draft_without_signals_ok():
    r = validate_opportunity(
        {
            "id": "opp_1",
            "status": "draft",
            "title": "t",
            "problem": "p",
            "audience": "a",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "signal_ids": [],
        }
    )
    assert r.ok, r.errors


def test_opportunity_hypothesized_requires_signals():
    r = validate_opportunity(
        {
            "id": "opp_1",
            "status": "hypothesized",
            "title": "t",
            "problem": "p",
            "audience": "a",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "signal_ids": [],
        }
    )
    assert not r.ok
    assert any("signal_ids" in e for e in r.errors)


def test_opportunity_requires_created_by():
    r = validate_opportunity(
        {
            "id": "opp_1",
            "status": "draft",
            "title": "t",
            "problem": "p",
            "audience": "a",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok
    assert any("created_by" in e for e in r.errors)


def test_opportunity_decided_requires_latest_decision_id():
    r = validate_opportunity(
        {
            "id": "opp_1",
            "status": "decided",
            "title": "t",
            "problem": "p",
            "audience": "a",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "signal_ids": ["sig_1"],
        }
    )
    assert not r.ok
    assert any("latest_decision_id" in e for e in r.errors)


def test_transition_blocks_hypothesized_to_building():
    r = validate_opportunity_transition("hypothesized", "building")
    assert not r.ok


def test_transition_blocks_experimenting_to_building():
    r = validate_opportunity_transition("experimenting", "building")
    assert not r.ok


def test_transition_experimenting_to_decided_ok():
    r = validate_opportunity_transition("experimenting", "decided")
    assert r.ok, r.errors


def test_transition_decided_branches():
    assert validate_opportunity_transition("decided", "building").ok
    assert validate_opportunity_transition("decided", "iterating").ok
    assert validate_opportunity_transition("decided", "killed").ok


def test_experiment_requires_created_by():
    r = validate_experiment(
        {
            "id": "exp_1",
            "opportunity_id": "opp_1",
            "status": "planned",
            "experiment_type": "smoke_page",
            "hypothesis_test": "test",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok
    assert any("created_by" in e for e in r.errors)


def test_experiment_running_requires_measurement_plan():
    base = {
        "id": "exp_1",
        "opportunity_id": "opp_1",
        "status": "running",
        "experiment_type": "waitlist",
        "hypothesis_test": "test",
        "created_by": "github:u",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    assert not validate_experiment(base).ok
    base["measurement_plan"] = "Count signups for 5 days in channel X"
    assert validate_experiment(base).ok


def test_experiment_threshold_optional():
    r = validate_experiment(
        {
            "id": "exp_1",
            "opportunity_id": "opp_1",
            "status": "planned",
            "experiment_type": "manual_pilot",
            "hypothesis_test": "test",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    assert r.ok, r.errors


def test_decision_requires_decided_by():
    r = validate_decision(
        {
            "id": "dec_1",
            "opportunity_id": "opp_1",
            "verdict": "kill",
            "reason": "no demand",
            "evidence_refs": ["sig_1"],
            "decided_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok


def test_decision_evidence_only_exp_or_sig():
    r = validate_decision(
        {
            "id": "dec_1",
            "opportunity_id": "opp_1",
            "verdict": "iterate",
            "reason": "weak signal",
            "evidence_refs": ["lr_1"],
            "decided_by": "human",
            "decided_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok
    assert any("exp_" in e or "sig_" in e for e in r.errors)


def test_decision_execute_without_evidence_fails():
    r = validate_decision(
        {
            "id": "dec_1",
            "opportunity_id": "opp_1",
            "verdict": "execute",
            "reason": "gut feel",
            "evidence_refs": [],
            "decided_by": "human",
            "decided_at": "2026-01-01T00:00:00Z",
        }
    )
    assert not r.ok


def test_decision_execute_with_evidence_ok():
    r = validate_decision(
        {
            "id": "dec_1",
            "opportunity_id": "opp_1",
            "verdict": "execute",
            "reason": "threshold met",
            "evidence_refs": ["exp_1"],
            "decided_by": "human",
            "decided_at": "2026-01-01T00:00:00Z",
        }
    )
    assert r.ok, r.errors


def test_learning_record_valid():
    r = validate_learning_record(
        {
            "id": "lr_1",
            "opportunity_id": "opp_1",
            "what_worked": "channel",
            "what_failed": "message",
            "created_at": "2026-01-01T00:00:00Z",
        }
    )
    assert r.ok, r.errors


def test_graph_resolves_refs():
    signals = {
        "sig_1": {
            "id": "sig_1",
            "source": "manual",
            "raw_text": "x",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    }
    opportunities = {
        "opp_1": {
            "id": "opp_1",
            "status": "experimenting",
            "title": "t",
            "problem": "p",
            "audience": "a",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "signal_ids": ["sig_1"],
            "active_experiment_id": "exp_1",
        }
    }
    experiments = {
        "exp_1": {
            "id": "exp_1",
            "opportunity_id": "opp_1",
            "status": "running",
            "experiment_type": "smoke_page",
            "hypothesis_test": "h",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "measurement_plan": "watch CTA for 7 days",
        }
    }
    r = validate_graph(
        signals=signals, opportunities=opportunities, experiments=experiments
    )
    assert r.ok, r.errors


def test_graph_broken_evidence_ref():
    signals = {
        "sig_1": {
            "id": "sig_1",
            "source": "manual",
            "raw_text": "x",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    }
    opportunities = {
        "opp_1": {
            "id": "opp_1",
            "status": "decided",
            "title": "t",
            "problem": "p",
            "audience": "a",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "signal_ids": ["sig_1"],
            "latest_decision_id": "dec_1",
        }
    }
    decisions = {
        "dec_1": {
            "id": "dec_1",
            "opportunity_id": "opp_1",
            "verdict": "execute",
            "reason": "ok",
            "evidence_refs": ["exp_missing"],
            "decided_by": "human",
            "decided_at": "2026-01-01T00:00:00Z",
        }
    }
    r = validate_graph(
        signals=signals, opportunities=opportunities, decisions=decisions
    )
    assert not r.ok
    assert any("not found" in e for e in r.errors)


def test_example_json_graph():
    path = ROOT / "contracts" / "examples" / "minimal_valid_graph.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    r = validate_graph(
        signals=data["signals"],
        opportunities=data["opportunities"],
        experiments=data["experiments"],
        decisions=data.get("decisions") or {},
        learnings=data.get("learnings") or {},
    )
    assert r.ok, r.errors


# --- Phase 1 corrections: active_experiment_id ---


def _opp_base(**kwargs):
    base = {
        "id": "opp_1",
        "status": "experimenting",
        "title": "t",
        "problem": "p",
        "audience": "a",
        "created_by": "github:u",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "signal_ids": ["sig_1"],
    }
    base.update(kwargs)
    return base


def test_experimenting_without_active_experiment_id_rejected():
    r = validate_opportunity(_opp_base())
    assert not r.ok
    assert any("active_experiment_id" in e for e in r.errors)


def test_experimenting_malformed_active_experiment_id_rejected():
    r = validate_opportunity(_opp_base(active_experiment_id="bad_id"))
    assert not r.ok
    assert any("active_experiment_id" in e for e in r.errors)


def test_experimenting_valid_active_experiment_id_accepted():
    r = validate_opportunity(_opp_base(active_experiment_id="exp_1"))
    assert r.ok, r.errors


def test_graph_missing_active_experiment_rejected():
    signals = {
        "sig_1": {
            "id": "sig_1",
            "source": "manual",
            "raw_text": "x",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    }
    opportunities = {
        "opp_1": _opp_base(active_experiment_id="exp_missing"),
    }
    r = validate_graph(signals=signals, opportunities=opportunities, experiments={})
    assert not r.ok
    assert any("not found" in e or "active_experiment" in e for e in r.errors)


def test_graph_valid_active_experiment_accepted():
    signals = {
        "sig_1": {
            "id": "sig_1",
            "source": "manual",
            "raw_text": "x",
            "captured_at": "2026-01-01T00:00:00Z",
        }
    }
    experiments = {
        "exp_1": {
            "id": "exp_1",
            "opportunity_id": "opp_1",
            "status": "running",
            "experiment_type": "smoke_page",
            "hypothesis_test": "h",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "measurement_plan": "watch CTA for 7 days",
        }
    }
    opportunities = {
        "opp_1": _opp_base(active_experiment_id="exp_1"),
    }
    r = validate_graph(
        signals=signals, opportunities=opportunities, experiments=experiments
    )
    assert r.ok, r.errors


# --- Phase 1 corrections: measurement_plan ---


def _exp_running(**kwargs):
    base = {
        "id": "exp_1",
        "opportunity_id": "opp_1",
        "status": "running",
        "experiment_type": "waitlist",
        "hypothesis_test": "test",
        "created_by": "github:u",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    base.update(kwargs)
    return base


def test_running_missing_measurement_plan_rejected():
    r = validate_experiment(_exp_running())
    assert not r.ok
    assert any("measurement_plan" in e for e in r.errors)


def test_running_empty_string_measurement_plan_rejected():
    r = validate_experiment(_exp_running(measurement_plan="  "))
    assert not r.ok


def test_running_text_measurement_plan_accepted():
    r = validate_experiment(
        _exp_running(measurement_plan="Measure waitlist signups over 7 days.")
    )
    assert r.ok, r.errors


def test_running_object_measurement_plan_accepted():
    r = validate_experiment(
        _exp_running(measurement_plan={"metric": "waitlist_signups", "window_days": 7})
    )
    assert r.ok, r.errors


def test_running_empty_object_measurement_plan_rejected():
    r = validate_experiment(_exp_running(measurement_plan={}))
    assert not r.ok


def test_planned_missing_measurement_plan_still_ok():
    r = validate_experiment(
        {
            "id": "exp_1",
            "opportunity_id": "opp_1",
            "status": "planned",
            "experiment_type": "manual_pilot",
            "hypothesis_test": "test",
            "created_by": "github:u",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    assert r.ok, r.errors


def test_transition_draft_to_building_rejected():
    r = validate_opportunity_transition("draft", "building")
    assert not r.ok
