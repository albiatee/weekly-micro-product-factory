"""Phase 2 — Signal Discovery tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.validate import validate_signal  # noqa: E402
from discovery.dedupe import find_duplicate, fingerprint  # noqa: E402
from discovery.normalize import candidate_to_signal_dict, generate_signal_id  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.sources.base import RawSignalCandidate  # noqa: E402
from discovery.store import list_signals, load_index  # noqa: E402


@pytest.fixture
def store(tmp_path: Path) -> Path:
    d = tmp_path / "signals"
    d.mkdir()
    return d


def test_generate_signal_id_prefix():
    assert generate_signal_id().startswith("sig_")


def test_valid_manual_signal_accepted(store: Path):
    result = ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Users want a simpler offline checklist",
            "captured_at": "2026-09-20T12:00:00Z",
            "language": "en",
            "geo_hint": "global",
        },
        store_root=store,
    )
    assert len(result.accepted) == 1
    assert len(result.rejected) == 0
    sig = result.accepted[0]["signal"]
    assert sig["id"].startswith("sig_")
    assert validate_signal(sig).ok
    assert sig["source"] == "manual"
    assert "offline checklist" in sig["raw_text"]
    assert sig["captured_at"] == "2026-09-20T12:00:00Z"
    stored = list_signals(store)
    assert sig["id"] in stored


def test_missing_source_rejected(store: Path):
    result = ingest_manual_payload(
        {"raw_text": "x", "captured_at": "2026-09-20T12:00:00Z", "source": ""},
        store_root=store,
    )
    # empty source fails validation
    assert len(result.rejected) >= 1 or len(result.accepted) == 0


def test_missing_raw_text_rejected(store: Path):
    result = ingest_manual_payload(
        {"source": "manual", "raw_text": "", "captured_at": "2026-09-20T12:00:00Z"},
        store_root=store,
    )
    assert len(result.rejected) == 1


def test_invalid_source_rejected(store: Path):
    result = ingest_manual_payload(
        {
            "source": "telegram",
            "raw_text": "complaint text here",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    assert len(result.rejected) == 1


def test_other_source_accepted(store: Path):
    result = ingest_manual_payload(
        {
            "source": "other",
            "raw_text": "Forum thread about inventory pain",
            "captured_at": "2026-09-20T12:00:00Z",
            "meta": {"source_detail": "local forum"},
        },
        store_root=store,
    )
    assert len(result.accepted) == 1
    assert result.accepted[0]["signal"]["meta"]["source_detail"] == "local forum"


def test_optional_fields_omitted_ok(store: Path):
    result = ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Minimal signal body text",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    assert len(result.accepted) == 1
    sig = result.accepted[0]["signal"]
    assert "language" not in sig
    assert "url" not in sig


def test_exact_duplicate_flagged(store: Path):
    payload = {
        "source": "manual",
        "raw_text": "Same complaint about pricing opacity",
        "captured_at": "2026-09-20T12:00:00Z",
    }
    r1 = ingest_manual_payload(payload, store_root=store)
    r2 = ingest_manual_payload(payload, store_root=store)
    assert len(r1.accepted) == 1
    assert len(r2.duplicates) == 1
    assert r2.duplicates[0]["duplicate_of"] == r1.accepted[0]["signal"]["id"]
    assert len(list_signals(store)) == 1


def test_normalized_duplicate_detected(store: Path):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Need simpler  invoicing",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    r2 = ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "  need simpler invoicing  ",
            "captured_at": "2026-09-21T12:00:00Z",
        },
        store_root=store,
    )
    assert len(r2.duplicates) == 1


def test_different_signals_remain_separate(store: Path):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Problem about shipping delays",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    r2 = ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Problem about tax forms",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    assert len(r2.accepted) == 1
    assert len(list_signals(store)) == 2


def test_url_duplicate(store: Path):
    ingest_manual_payload(
        {
            "source": "review",
            "raw_text": "First comment",
            "url": "https://example.com/review/1",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    r2 = ingest_manual_payload(
        {
            "source": "review",
            "raw_text": "Different wording",
            "url": "https://example.com/review/1",
            "captured_at": "2026-09-20T13:00:00Z",
        },
        store_root=store,
    )
    assert len(r2.duplicates) == 1


def test_provenance_preserved(store: Path):
    result = ingest_manual_payload(
        {
            "source": "reddit",
            "raw_text": "Original observation text",
            "captured_at": "2026-09-20T12:00:00Z",
            "url": "https://reddit.com/r/x/1",
            "created_by": "github:tester",
        },
        store_root=store,
    )
    sig = result.accepted[0]["signal"]
    assert sig["source"] == "reddit"
    assert sig["raw_text"] == "Original observation text"
    assert sig["captured_at"] == "2026-09-20T12:00:00Z"
    assert sig["url"] == "https://reddit.com/r/x/1"
    assert sig["created_by"] == "github:tester"


def test_fingerprint_stable():
    a = fingerprint({"raw_text": "  Hello   World "})
    b = fingerprint({"raw_text": "hello world"})
    assert a == b


def test_no_opportunity_keys_in_store(store: Path):
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": "Just a signal",
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=store,
    )
    data = load_index(store)
    assert "opportunities" not in data
    assert "signals" in data
