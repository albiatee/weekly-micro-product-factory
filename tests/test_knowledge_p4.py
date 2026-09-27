"""P4 Knowledge & Similarity — advisory, deterministic, read-only."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from knowledge.normalize import tokenize, token_set
from knowledge.similarity import jaccard, score_pair, score_text
from knowledge.search import compare_idea, search
from knowledge.index import build_corpus


def test_score_bounds():
    s, terms = score_text("inventory spreadsheet stockout", "inventory spreadsheet causes stockout")
    assert 0.0 <= s <= 1.0
    assert isinstance(terms, list)


def test_empty_query():
    r = search("")
    assert r["count"] == 0
    assert r["decision"] is None
    assert r["advisory"] is True


def test_exact_near_duplicate_ranks_high():
    corpus_q = "ecommerce inventory spreadsheets fail multi channel stockouts"
    r = search(corpus_q, limit=5, min_score=0.05)
    assert r["advisory"] is True
    assert r["decision"] is None
    if r["count"] == 0:
        pytest.skip("no matching historical data in store")
    # top score should be meaningful
    assert r["matches"][0]["similarity_score"] >= 0.15
    assert r["matches"][0]["entity_type"] in (
        "signal",
        "opportunity",
        "product",
        "experiment",
        "decision",
        "learning",
    )


def test_related_but_different():
    r = search("plumbing appointment no-show reminders for small shops", limit=8, min_score=0.05)
    assert r["decision"] is None
    # may or may not match depending on data; structure must hold
    for m in r["matches"]:
        assert 0.0 <= m["similarity_score"] <= 1.0
        assert "matched_terms" in m


def test_unrelated_low_or_empty():
    r = search("quantum entanglement cookbook recipes for astronauts", limit=5, min_score=0.2)
    # unrelated should not flood high scores
    for m in r["matches"]:
        assert m["similarity_score"] < 0.85


def test_deterministic_ordering():
    q = "spreadsheet inventory orders"
    a = search(q, limit=10, min_score=0.05)
    b = search(q, limit=10, min_score=0.05)
    assert [m["entity_id"] for m in a["matches"]] == [m["entity_id"] for m in b["matches"]]
    assert [m["similarity_score"] for m in a["matches"]] == [
        m["similarity_score"] for m in b["matches"]
    ]


def test_missing_stores(tmp_path):
    r = search("inventory", root=tmp_path, limit=5)
    assert r["count"] == 0
    assert r["corpus_size"] == 0
    assert r["decision"] is None


def test_no_fabricated_outcomes():
    r = compare_idea("inventory spreadsheet multi-channel overselling", limit=3)
    assert r["decision"] is None
    for c in r["comparisons"]:
        assert c["previous_outcome"] in (
            "not available",
            None,
        ) or isinstance(c["previous_outcome"], str)
        # must not invent boolean success
        assert c["previous_outcome"] is not True
        assert c.get("learning_evidence") is None or isinstance(
            c.get("learning_evidence"), str
        )


def test_jaccard_identity():
    t = token_set("alpha beta gamma")
    assert jaccard(t, t) == 1.0
    assert jaccard(frozenset(), frozenset("a")) == 0.0


def test_read_only_search_does_not_write(tmp_path):
    # copy minimal signal into isolated root is optional; hash project data
    opp = ROOT / "data" / "opportunities" / "index.json"
    pre = hashlib.sha256(opp.read_bytes()).hexdigest() if opp.exists() else None
    search("inventory spreadsheet", limit=3)
    post = hashlib.sha256(opp.read_bytes()).hexdigest() if opp.exists() else None
    assert pre == post


def test_api_knowledge_search():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app, set_root_override

    set_root_override(None)
    c = TestClient(app)
    r = c.get("/knowledge/search", params={"q": "inventory spreadsheet", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["advisory"] is True
    assert body["decision"] is None
    assert "matches" in body


def test_api_knowledge_compare():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app

    c = TestClient(app)
    r = c.get("/knowledge/compare", params={"q": "no show plumbing reminders"})
    assert r.status_code == 200
    body = r.json()
    assert body["advisory"] is True
    assert body["decision"] is None


def test_api_empty_query():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api.app import app

    c = TestClient(app)
    r = c.get("/knowledge/search", params={"q": ""})
    assert r.status_code == 200
    assert r.json()["count"] == 0
