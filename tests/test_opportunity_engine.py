"""Phase 3 — Opportunity Engine tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.validate import validate_opportunity  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from opportunity.generate import build_opportunity_from_signals  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids, generate_from_store  # noqa: E402
from opportunity.store import list_opportunities  # noqa: E402


@pytest.fixture
def stores(tmp_path: Path):
    sig = tmp_path / "signals"
    opp = tmp_path / "opportunities"
    sig.mkdir()
    opp.mkdir()
    return sig, opp


def _seed_signal(store: Path, text: str = "Freelancers struggle every week because they cannot match payments and waste hours reconciling invoices manually.", **extra):
    payload = {
        "source": "manual",
        "raw_text": text,
        "captured_at": "2026-09-20T12:00:00Z",
        **extra,
    }
    r = ingest_manual_payload(payload, store_root=store)
    assert r.accepted, r.rejected
    return r.accepted[0]["signal"]


def test_valid_signal_to_opportunity(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    result = generate_from_signal_ids(
        [sig["id"]], signals_root=sig_store, opportunities_root=opp_store
    )
    assert len(result.accepted) == 1
    opp = result.accepted[0]["opportunity"]
    assert opp["id"].startswith("opp_")
    assert opp["status"] == "hypothesized"
    assert sig["id"] in opp["signal_ids"]
    assert validate_opportunity(opp).ok


def test_multiple_signals_one_opportunity(stores):
    sig_store, opp_store = stores
    s1 = _seed_signal(sig_store, "Freelancers struggle with invoicing every month and cannot find a simple offline tool")
    s2 = _seed_signal(sig_store, "Invoicing is too complex offline; teams manually use spreadsheets as a workaround")
    result = generate_from_signal_ids(
        [s1["id"], s2["id"]],
        signals_root=sig_store,
        opportunities_root=opp_store,
        combine=True,
    )
    assert len(result.accepted) == 1
    opp = result.accepted[0]["opportunity"]
    assert set(opp["signal_ids"]) == {s1["id"], s2["id"]}


def test_preserves_signal_ids(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    opp = build_opportunity_from_signals([sig])
    assert opp["signal_ids"] == [sig["id"]]


def test_missing_signal_reference_rejected(stores):
    sig_store, opp_store = stores
    result = generate_from_signal_ids(
        ["sig_does_not_exist"],
        signals_root=sig_store,
        opportunities_root=opp_store,
    )
    assert len(result.rejected) == 1
    assert len(result.accepted) == 0


def test_empty_signals_rejected():
    with pytest.raises(ValueError):
        build_opportunity_from_signals([])


def test_required_fields_and_hypothesized(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    opp = build_opportunity_from_signals([sig])
    for key in (
        "id",
        "status",
        "title",
        "problem",
        "audience",
        "created_by",
        "created_at",
        "updated_at",
        "signal_ids",
        "value_proposition",
        "hypothesis",
        "solution_type",
        "geo",
        "score",
    ):
        assert key in opp
    assert opp["status"] == "hypothesized"
    assert "[HYPOTHESIS]" in opp["hypothesis"]


def test_solution_type_valid(stores):
    sig_store, _ = stores
    sig = _seed_signal(sig_store, "Need a template pack for resumes")
    opp = build_opportunity_from_signals([sig])
    assert opp["solution_type"] in {
        "digital_micro",
        "content_pack",
        "concierge",
        "saas",
        "physical_hybrid",
        "marketplace",
        "unknown",
    }


def test_geo_structure(stores):
    sig_store, _ = stores
    sig = _seed_signal(sig_store, "Issue in market", geo_hint="SA", language="ar")
    opp = build_opportunity_from_signals([sig])
    geo = opp["geo"]
    assert "primary" in geo and "region" in geo and "languages" in geo and "rationale" in geo


def test_score_values_0_100(stores):
    sig_store, _ = stores
    sig = _seed_signal(sig_store)
    opp = build_opportunity_from_signals([sig])
    for k, v in opp["score"].items():
        assert isinstance(v, int)
        assert 0 <= v <= 100


def test_deterministic_scoring(stores):
    sig_store, _ = stores
    sig = _seed_signal(sig_store, "Stable text for scoring determinism")
    a = build_opportunity_from_signals([sig], opportunity_id="opp_a")
    b = build_opportunity_from_signals([sig], opportunity_id="opp_b")
    assert a["score"] == b["score"]
    assert a["solution_type"] == b["solution_type"]


def test_no_fabricated_market_size_fields(stores):
    sig_store, _ = stores
    sig = _seed_signal(sig_store)
    opp = build_opportunity_from_signals([sig])
    blob = json_dumps(opp)
    for banned in ("market_size", "revenue_estimate", "conversion_rate", "TAM", "SAM"):
        assert banned not in blob


def json_dumps(obj):
    import json

    return json.dumps(obj)


def test_duplicate_handling(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    r1 = generate_from_signal_ids(
        [sig["id"]], signals_root=sig_store, opportunities_root=opp_store
    )
    r2 = generate_from_signal_ids(
        [sig["id"]], signals_root=sig_store, opportunities_root=opp_store
    )
    assert len(r1.accepted) == 1
    assert len(r2.duplicates) == 1
    assert len(list_opportunities(opp_store)) == 1


def test_no_silent_overwrite(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    generate_from_signal_ids(
        [sig["id"]], signals_root=sig_store, opportunities_root=opp_store
    )
    first_id = list(list_opportunities(opp_store).keys())[0]
    generate_from_signal_ids(
        [sig["id"]], signals_root=sig_store, opportunities_root=opp_store
    )
    assert list(list_opportunities(opp_store).keys()) == [first_id]


def test_lifecycle_stays_hypothesized(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    r = generate_from_store(signals_root=sig_store, opportunities_root=opp_store)
    assert r.accepted
    for item in r.accepted:
        assert item["opportunity"]["status"] == "hypothesized"
        assert item["opportunity"]["status"] not in {
            "experimenting",
            "decided",
            "building",
            "shipped",
            "killed",
        }


def test_does_not_create_experiments_or_decisions(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    r = generate_from_signal_ids(
        [sig["id"]], signals_root=sig_store, opportunities_root=opp_store
    )
    opp = r.accepted[0]["opportunity"]
    assert "experiment_id" not in opp or opp.get("active_experiment_id") in (None, "")
    assert opp.get("latest_decision_id") in (None, "",)


def test_dry_run_no_persist(stores):
    sig_store, opp_store = stores
    sig = _seed_signal(sig_store)
    r = generate_from_signal_ids(
        [sig["id"]],
        signals_root=sig_store,
        opportunities_root=opp_store,
        dry_run=True,
    )
    assert len(r.accepted) == 1
    assert list_opportunities(opp_store) == {}
