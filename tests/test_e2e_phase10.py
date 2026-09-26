"""Phase 10 — deterministic E2E pilot through Phases 1–9.

SYSTEM VALIDATION only. Synthetic pilot fixtures. NOT real market validation.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analytics.pipeline import generate_learning_records, run_analytics  # noqa: E402
from analytics.store import list_learnings  # noqa: E402
from decision.pipeline import create_decision  # noqa: E402
from discovery.pipeline import ingest_manual_payload  # noqa: E402
from discovery.store import list_signals  # noqa: E402
from discovery_feedback.pipeline import (  # noqa: E402
    approve_hint,
    convert_to_signal,
    create_hint_from_learning,
)
from discovery_feedback.store import list_hints  # noqa: E402
from distribution.from_spec import create_distribution_from_spec, prepare_distribution, record_publication  # noqa: E402
from distribution.store import list_plans  # noqa: E402
from experiment.pipeline import (  # noqa: E402
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)
from opportunity.evidence import is_evidence_ready  # noqa: E402
from opportunity.pipeline import generate_from_signal_ids  # noqa: E402
from opportunity.store import list_opportunities, upsert_opportunity  # noqa: E402
from production.pipeline import create_production_spec  # noqa: E402
from production.store import list_production_specs  # noqa: E402

# --- Pilot fixture (synthetic / test evidence only) ---
PILOT_SIGNAL_TEXT = (
    "[PILOT FIXTURE — synthetic/test evidence, not real market validation] "
    "Shop owners struggle every week because they waste several hours reconciling "
    "invoices manually without a simple offline tool that works without internet. "
    "They need a lightweight checklist or tracker to reduce repeated errors."
)


def _roots(tmp_path: Path) -> dict[str, Path]:
    names = ("sig", "opp", "exp", "dec", "prd", "dist", "an", "hints")
    out = {}
    for n in names:
        p = tmp_path / n
        p.mkdir()
        out[n] = p
    return out


def run_pilot(roots: dict[str, Path]) -> dict:
    """Execute full V2 lifecycle once. Returns chain dict for assertions/report."""
    chain: dict = {"label": "phase10_synthetic_pilot"}

    # A–B Signal + Quality
    ingest_manual_payload(
        {
            "source": "manual",
            "raw_text": PILOT_SIGNAL_TEXT,
            "captured_at": "2026-09-20T12:00:00Z",
            "created_by": "pilot:phase10",
        },
        store_root=roots["sig"],
    )
    signals = list_signals(roots["sig"])
    assert len(signals) == 1
    sid = list(signals.keys())[0]
    sig = signals[sid]
    assert sig.get("qualification_status") == "qualified", sig
    assert sig.get("intent_type")
    assert sig.get("evidence_strength")
    chain["signal_id"] = sid
    chain["qualification"] = sig["qualification_status"]

    # C Opportunity + evidence
    g = generate_from_signal_ids(
        [sid], signals_root=roots["sig"], opportunities_root=roots["opp"]
    )
    assert g.accepted, getattr(g, "rejected", None) or g
    oid = g.accepted[0]["opportunity"]["id"]
    opp = list_opportunities(roots["opp"])[oid]
    # ensure digital_micro for optional downstream
    if not opp.get("solution_type"):
        opp = {**opp, "solution_type": "digital_micro"}
        upsert_opportunity(opp, roots["opp"])
        opp = list_opportunities(roots["opp"])[oid]
    ready, errs = is_evidence_ready(opp)
    assert ready, errs
    assert sid in (opp.get("signal_ids") or [])
    chain["opportunity_id"] = oid
    chain["evidence_ready"] = True

    # D Experiment
    er = create_experiment(
        oid,
        experiment_type="waitlist",
        measurement_plan=(
            "Count qualified pilot waitlist signups over 14 synthetic days "
            "(operator-recorded; not real traffic)."
        ),
        success_criteria=(
            "At least 10 synthetic pilot signups recorded by operator "
            "in experiment results metrics."
        ),
        failure_criteria=(
            "Fewer than 3 synthetic pilot signups after the observation window."
        ),
        target_population="Small shop owners (pilot fixture audience)",
        hypothesis_test="An offline invoice checklist reduces weekly reconciliation time.",
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
    )
    assert er.ok, er.errors
    eid = er.experiment["id"]

    sr = start_experiment(
        eid, opportunities_root=roots["opp"], experiments_root=roots["exp"]
    )
    assert sr.ok, sr.errors
    rr = record_results(
        eid,
        metrics={"signups": 12, "note": "synthetic pilot values only"},
        qualitative_notes="Phase 10 pilot fixture results — not real market demand.",
        experiments_root=roots["exp"],
    )
    assert rr.ok, rr.errors
    cr = complete_experiment(
        eid, experiments_root=roots["exp"], opportunities_root=roots["opp"]
    )
    assert cr.ok, cr.errors
    chain["experiment_id"] = eid
    chain["experiment_status"] = "completed"

    # E Decision execute
    dres = create_decision(
        opportunity_id=oid,
        verdict="execute",
        reason=(
            "Phase 10 pilot: predefined success_criteria met with operator-recorded "
            "synthetic metrics (signups=12). Authorizes production specification only; "
            "not a claim of real product-market fit."
        ),
        evidence_refs=[eid],
        decided_by="human",
        experiment_id=eid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        signals_root=roots["sig"],
        decisions_root=roots["dec"],
    )
    assert dres.ok, dres.errors
    did = dres.decision["id"]
    assert dres.decision.get("criteria_snapshot")
    assert dres.decision.get("metrics_snapshot") is not None
    chain["decision_id"] = did
    chain["verdict"] = "execute"

    # F Production Spec
    pres = create_production_spec(
        decision_id=did,
        opportunities_root=roots["opp"],
        decisions_root=roots["dec"],
        experiments_root=roots["exp"],
        production_root=roots["prd"],
    )
    assert pres.ok, pres.errors
    prd_id = pres.production_spec["id"]
    assert sid in (pres.production_spec.get("source_signal_ids") or [])
    assert pres.production_spec["decision_id"] == did
    chain["production_spec_id"] = prd_id

    # G Distribution
    dres2 = create_distribution_from_spec(
        prd_id,
        channel="landing_page",
        message="Pilot distribution plan text (synthetic; not published externally).",
        production_root=roots["prd"],
        decisions_root=roots["dec"],
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        distribution_root=roots["dist"],
    )
    assert dres2["ok"], dres2["errors"]
    dist_id = dres2["plan"]["id"]
    assert dres2["plan"]["status"] == "planned"
    prep = prepare_distribution(dist_id, distribution_root=roots["dist"])
    assert prep["ok"]
    pub = record_publication(
        dist_id,
        success=True,
        destination_url="https://example.invalid/pilot-phase10",
        notes="Synthetic destination only — no external publish.",
        distribution_root=roots["dist"],
    )
    assert pub["ok"]
    assert pub["plan"]["status"] == "published"
    chain["distribution_id"] = dist_id
    chain["distribution_status"] = "published"

    # H Analytics
    ares = run_analytics(
        opportunity_id=oid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        signals_root=roots["sig"],
        distribution_root=roots["dist"],
        production_root=roots["prd"],
        analytics_root=roots["an"],
    )
    assert ares.ok
    funnel = (ares.snapshot or {}).get("funnel") or {}
    chain["funnel_stages"] = [s.get("stage") for s in funnel.get("stages") or []]

    # I Learning
    lres = generate_learning_records(
        opportunity_id=oid,
        opportunities_root=roots["opp"],
        experiments_root=roots["exp"],
        decisions_root=roots["dec"],
        distribution_root=roots["dist"],
        analytics_root=roots["an"],
    )
    assert lres.ok, lres.errors
    assert lres.learnings, "expected LearningRecord"
    lr = lres.learnings[0]
    lid = lr["id"]
    assert lr.get("opportunity_id") == oid
    chain["learning_id"] = lid

    # J Closed loop
    hres = create_hint_from_learning(
        lid,
        learnings_root=roots["an"],
        opportunities_root=roots["opp"],
        hints_root=roots["hints"],
    )
    assert hres.ok, hres.errors
    hid = hres.hint["id"]
    assert hres.hint["status"] == "proposed"
    # cannot convert without approve
    from discovery_feedback.pipeline import convert_to_signal as _conv

    assert not _conv(
        hid,
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    ).ok
    ap = approve_hint(
        hid,
        reviewed_by="pilot:human",
        review_notes="Phase 10 human gate — approve discovery hint only.",
        hints_root=roots["hints"],
    )
    assert ap.ok
    n_sig_before = len(list_signals(roots["sig"]))
    n_opp_before = len(list_opportunities(roots["opp"]))
    c1 = convert_to_signal(
        hid,
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    )
    assert c1.ok, c1.errors
    new_sid = c1.signal["id"]
    assert c1.signal["meta"]["discovery_hint_id"] == hid
    assert c1.signal["meta"]["source_learning_id"] == lid
    assert c1.signal["meta"]["source_opportunity_id"] == oid
    # quality fields present
    assert c1.signal.get("qualification_status")
    assert len(list_signals(roots["sig"])) == n_sig_before + 1
    assert len(list_opportunities(roots["opp"])) == n_opp_before

    # idempotent conversion
    c2 = convert_to_signal(
        hid,
        hints_root=roots["hints"],
        signals_root=roots["sig"],
        opportunities_root=roots["opp"],
    )
    assert c2.ok
    assert c2.signal["id"] == new_sid
    assert len(list_signals(roots["sig"])) == n_sig_before + 1

    chain["discovery_hint_id"] = hid
    chain["converted_signal_id"] = new_sid
    chain["traceability"] = "PASS"
    chain["idempotency"] = "PASS"
    chain["human_gate"] = "PASS"
    return chain


def test_e2e_phase10_happy_path(tmp_path):
    chain = run_pilot(_roots(tmp_path))
    assert chain["qualification"] == "qualified"
    assert chain["evidence_ready"] is True
    assert chain["experiment_status"] == "completed"
    assert chain["verdict"] == "execute"
    assert chain["production_spec_id"].startswith("prd_")
    assert chain["distribution_status"] == "published"
    assert chain["learning_id"].startswith("lr_")
    assert chain["converted_signal_id"].startswith("sig_")
    assert chain["traceability"] == "PASS"
    assert chain["human_gate"] == "PASS"
    assert chain["idempotency"] == "PASS"


def test_e2e_phase10_traceability_ids(tmp_path):
    roots = _roots(tmp_path)
    chain = run_pilot(roots)
    # Cross-check stores
    sig = list_signals(roots["sig"])[chain["signal_id"]]
    opp = list_opportunities(roots["opp"])[chain["opportunity_id"]]
    assert chain["signal_id"] in (opp.get("signal_ids") or [])
    specs = list_production_specs(roots["prd"])
    assert specs[chain["production_spec_id"]]["experiment_id"] == chain["experiment_id"]
    plans = list_plans(roots["dist"])
    assert plans[chain["distribution_id"]]["production_spec_id"] == chain["production_spec_id"]
    lr = list_learnings(roots["an"])[chain["learning_id"]]
    assert lr["opportunity_id"] == chain["opportunity_id"]
    hint = list_hints(roots["hints"])[chain["discovery_hint_id"]]
    assert hint["source_learning_id"] == chain["learning_id"]
