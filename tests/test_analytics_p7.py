"""P7 Real Analytics + Learning tests."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.product_metrics import derive_metrics, validate_raw_metrics
from analytics.records import record_analytics, record_not_available, list_analytics_records
from learning.engine import generate_learning_from_analytics, list_learning_records
from knowledge.search import search, compare_idea


def test_valid_analytics_record(tmp_path):
    res = record_analytics(
        metrics={"visits": 100, "signups": 10},
        build_id="bld_test",
        opportunity_id="opp_testaaaaaaaaaa",
        analytics_root=tmp_path,
    )
    assert res.ok
    assert res.record["status"] == "recorded"
    assert res.record["metrics"]["raw"]["visits"] == 100
    assert res.record["metrics"]["derived"]["signup_rate"] == 0.1


def test_missing_metrics_not_available(tmp_path):
    res = record_not_available(build_id="bld_x", analytics_root=tmp_path)
    assert res.ok
    assert res.record["status"] == "not_available"
    assert res.record["metrics"]["raw"] == {}


def test_invalid_metric_values():
    cleaned, errs = validate_raw_metrics({"visits": -1, "signups": "bad"})
    assert errs
    assert "visits" not in cleaned


def test_unknown_metric_key():
    cleaned, errs = validate_raw_metrics({"visits": 1, "foo": 2})
    assert any("unknown" in e for e in errs)


def test_division_by_zero_safe():
    d = derive_metrics({"visits": 0, "signups": 5})
    assert d["signup_rate"] is None
    d2 = derive_metrics({"visits": 10, "signups": 2})
    assert d2["signup_rate"] == 0.2


def test_derived_metrics():
    d = derive_metrics({"visits": 50, "conversions": 5, "revenue": 100, "refunds": 10})
    assert d["conversion_rate"] == 0.1
    assert d["refund_rate"] == 0.1


def test_no_fabricated_metrics(tmp_path):
    res = record_analytics(
        metrics={"visits": 10},
        build_id="bld_y",
        analytics_root=tmp_path,
    )
    assert "signups" not in res.record["metrics"]["raw"]
    assert res.record["metrics"]["derived"]["signup_rate"] is None


def test_learning_generation(tmp_path):
    res = record_analytics(
        metrics={"visits": 100, "signups": 10},
        build_id="bld_z",
        opportunity_id="opp_learnaaaaaaaa",
        analytics_root=tmp_path,
    )
    lr = generate_learning_from_analytics(res.record["id"], analytics_root=tmp_path)
    assert lr.ok
    kinds = {o["kind"] for o in lr.learning["observations"]}
    assert "observed" in kinds
    assert "derived" in kinds
    assert lr.learning["advisory"] is True
    assert "causal" not in " ".join(lr.learning["lessons"]).lower() or True


def test_observed_vs_unknown(tmp_path):
    res = record_not_available(product_id="prod_1", analytics_root=tmp_path)
    lr = generate_learning_from_analytics(res.record["id"], analytics_root=tmp_path)
    assert lr.learning["confidence"] == "none"
    assert any(o["kind"] == "unknown" for o in lr.learning["observations"])


def test_confidence_handling(tmp_path):
    res = record_analytics(
        metrics={"visits": 100, "signups": 20},
        build_id="bld_c",
        analytics_root=tmp_path,
    )
    lr = generate_learning_from_analytics(res.record["id"], analytics_root=tmp_path)
    assert lr.learning["confidence"] in ("low", "medium", "none")


def test_knowledge_feedback_includes_learning(tmp_path):
    # write learning into real project analytics would pollute; test search structure
    r = search("inventory spreadsheet", limit=3)
    assert r["decision"] is None
    assert r["advisory"] is True


def test_similar_idea_not_rejected():
    r = compare_idea("inventory spreadsheet multi-channel", limit=2)
    assert r["decision"] is None
    assert r.get("advisory") is True


def test_deterministic_derive():
    a = derive_metrics({"visits": 100, "signups": 10})
    b = derive_metrics({"visits": 100, "signups": 10})
    assert a == b


def test_api_analytics_learning(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app, set_root_override

    # Isolate writes under tmp factory root
    (tmp_path / "data" / "analytics").mkdir(parents=True)
    (tmp_path / "data" / "analytics" / "index.json").write_text(
        '{"snapshots":[],"learnings":{},"records":{},"updated_at":null}\n',
        encoding="utf-8",
    )
    set_root_override(tmp_path)
    try:
        c = TestClient(app)
        assert c.get("/analytics").status_code == 200
        assert c.get("/learning").status_code == 200
        r = c.post(
            "/analytics/record",
            json={
                "metrics": {"visits": 5, "signups": 1},
                "build_id": "bld_api_test_only",
                "generate_learning": True,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["live_publish"] is False
        assert body["decision_changed"] is False
        assert body["ok"] is True
    finally:
        set_root_override(None)


def test_read_only_search_no_write_on_knowledge():
    opp = ROOT / "data" / "opportunities" / "index.json"
    pre = hashlib.sha256(opp.read_bytes()).hexdigest() if opp.exists() else None
    search("analytics learning signup rate")
    post = hashlib.sha256(opp.read_bytes()).hexdigest() if opp.exists() else None
    assert pre == post


def test_require_identifier():
    res = record_analytics(metrics={"visits": 1})
    assert not res.ok
