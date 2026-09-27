"""P3 Backend API tests — read-only + dry-run only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from api.app import app, set_root_override


@pytest.fixture
def client():
    set_root_override(None)
    return TestClient(app)


@pytest.fixture
def isolated_root(tmp_path):
    # minimal empty factory layout
    for name in (
        "signals",
        "opportunities",
        "experiments",
        "decisions",
        "production",
        "distribution",
        "analytics",
        "cycles",
    ):
        d = tmp_path / "data" / name
        d.mkdir(parents=True)
        (d / "index.json").write_text(json.dumps({name if name != "analytics" else "learnings": {}, "updated_at": None}) + "\n")
    # fix keys to match readers
    (tmp_path / "data" / "signals" / "index.json").write_text(
        json.dumps({"signals": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "opportunities" / "index.json").write_text(
        json.dumps({"opportunities": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "experiments" / "index.json").write_text(
        json.dumps({"experiments": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "decisions" / "index.json").write_text(
        json.dumps({"decisions": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "cycles" / "index.json").write_text(
        json.dumps({"cycles": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "production" / "index.json").write_text(
        json.dumps({"production_specs": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "distribution" / "index.json").write_text(
        json.dumps({"plans": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "data" / "analytics" / "index.json").write_text(
        json.dumps({"learnings": {}, "updated_at": None}) + "\n"
    )
    (tmp_path / "products" / "weekly").mkdir(parents=True)
    set_root_override(tmp_path)
    yield tmp_path
    set_root_override(None)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["live_execution"] is False


@pytest.mark.parametrize(
    "path",
    [
        "/signals",
        "/opportunities",
        "/experiments",
        "/decisions",
        "/production-specs",
        "/distributions",
        "/learning",
        "/cycles",
        "/products",
    ],
)
def test_get_endpoints_real_or_empty(client, path):
    r = client.get(path)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body or "count" in body
    assert isinstance(body.get("count", len(body.get("items", {}))), int)


def test_empty_stores(isolated_root):
    c = TestClient(app)
    for path in ("/signals", "/opportunities", "/experiments", "/cycles", "/products"):
        r = c.get(path)
        assert r.status_code == 200
        assert r.json()["count"] == 0


def test_malformed_store(isolated_root):
    bad = isolated_root / "data" / "signals" / "index.json"
    bad.write_text("{not-json", encoding="utf-8")
    c = TestClient(app)
    r = c.get("/signals")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert body.get("store_status") in ("error", "ok", "missing")


def test_dry_run_endpoint(client):
    # uses real project root — may generate opportunities; force no persist
    r = client.post("/cycles/dry-run", json={"stop_after": "SELECT", "persist": False})
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True
    assert body["live_forbidden"] is True
    if body["ok"]:
        cycle = body["cycle"]
        assert cycle.get("dry_run") is True
        assert cycle.get("status") in ("completed", "aborted", "failed")


def test_live_cycle_forbidden(client):
    r = client.post("/cycles/live")
    assert r.status_code == 403


def test_publish_build_forbidden(client):
    assert client.post("/publish").status_code == 403
    assert client.post("/build").status_code == 403


def test_api_does_not_require_live_flag(client):
    """Body cannot enable live — only dry_run path exists."""
    r = client.post("/cycles/dry-run", json={"stop_after": "QUALIFY", "persist": False})
    assert r.status_code == 200
    assert r.json()["dry_run"] is True


def test_products_shape(client):
    r = client.get("/products")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["count"] >= 0
