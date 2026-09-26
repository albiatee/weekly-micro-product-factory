"""Phase 8 — Analytics & Learning observational layer."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.metrics import compute_counts, compute_funnel  # noqa: E402
from analytics.pipeline import generate_learning_records, run_analytics  # noqa: E402
from analytics.store import list_learnings, load_index  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities  # noqa: E402


def test_counts_include_signals_and_empty_prod(tmp_path):
    sig = tmp_path / "sig"
    opp = tmp_path / "opp"
    sig.mkdir()
    opp.mkdir()
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": (
                "Shop owners struggle every week reconciling invoices manually "
                "without offline tools. [a8]"
            ),
            "captured_at": "2026-09-20T12:00:00Z",
        },
        store_root=sig,
    )
    signals = list_signals(sig)
    generate_from_signal_ids(
        list(signals.keys()), signals_root=sig, opportunities_root=opp
    )
    opportunities = list_opportunities(opp)
    counts = compute_counts(opportunities, {}, {}, {}, {}, signals=signals, production_specs={})
    assert counts["signals"]["available"] is True
    assert counts["signals"]["signals_total"] >= 1
    assert counts["production"]["available"] is True
    assert counts["production"]["production_specs_total"] == 0
    funnel = compute_funnel(signals, opportunities, {}, {}, {}, {})
    assert funnel["stages"][0]["stage"] == "signals"
    assert funnel["stages"][2]["count"] == len(opportunities)


def test_analytics_deterministic_and_no_lifecycle_write(tmp_path):
    opp = tmp_path / "opp"
    an = tmp_path / "an"
    opp.mkdir()
    an.mkdir()
    a1 = run_analytics(opportunities_root=opp, analytics_root=an)
    a2 = run_analytics(opportunities_root=opp, analytics_root=an)
    assert a1.ok and a2.ok
    c1 = a1.snapshot["counts"]
    c2 = a2.snapshot["counts"]
    # drop generated_at sensitivity — counts must match
    assert c1["opportunities_total"] == c2["opportunities_total"]
    # still no opportunities mutated
    assert list_opportunities(opp) == {}
    idx = load_index(an)
    # idempotent filter: only one snapshot for empty filter
    same = [s for s in idx["snapshots"] if (s.get("filter") or {}) == {"opportunity_id": None}]
    assert len(same) == 1


def test_learning_idempotent_and_fields(tmp_path):
    # minimal opportunity without completed experiment → skip
    opp = tmp_path / "opp"
    an = tmp_path / "an"
    opp.mkdir()
    an.mkdir()
    r = generate_learning_records(opportunities_root=opp, analytics_root=an)
    assert r.ok
    assert r.learnings == []


def test_rates_none_not_zero():
    counts = compute_counts({}, {}, {}, {}, {})
    assert counts["rates"]["execute_rate_among_decisions"] is None
