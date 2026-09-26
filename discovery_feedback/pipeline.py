"""Discovery Feedback pipeline: Learning → Hint → Human Review → Signal.

Does not auto-create Opportunities or Decisions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analytics.store import list_learnings
from discovery.pipeline import process_candidate
from discovery.sources.base import RawSignalCandidate
from discovery.store import list_signals
from opportunity.store import list_opportunities

from .build import build_hint_from_learning, normalize_hint_text
from .constants import ACTIVE_FOR_DEDUP, FEEDBACK_TYPES
from .store import list_hints, upsert_hint
from .validate import validate_hint, validate_hint_transition


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class HintResult:
    ok: bool
    hint: dict[str, Any] | None = None
    signal: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def create_hint_from_learning(
    learning_id: str,
    *,
    learnings_root: Path | None = None,
    opportunities_root: Path | None = None,
    hints_root: Path | None = None,
    created_by: str = "system:discovery_feedback",
    feedback_type: str = "other",
    dry_run: bool = False,
) -> HintResult:
    learnings = list_learnings(learnings_root)
    lr = learnings.get(learning_id)
    if not lr:
        return HintResult(False, errors=[f"learning not found: {learning_id}"])
    oid = lr.get("opportunity_id")
    if oid and oid not in list_opportunities(opportunities_root):
        return HintResult(False, errors=[f"opportunity not found: {oid}"])
    try:
        hint = build_hint_from_learning(
            lr, created_by=created_by, feedback_type=feedback_type
        )
    except ValueError as e:
        return HintResult(False, errors=[str(e)])

    norm = normalize_hint_text(hint["hint"])
    for existing in list_hints(hints_root).values():
        if existing.get("source_learning_id") != learning_id:
            continue
        if normalize_hint_text(existing.get("hint") or "") != norm:
            continue
        if existing.get("status") in ACTIVE_FOR_DEDUP:
            return HintResult(
                False,
                hint=existing,
                errors=[
                    f"duplicate active hint for learning {learning_id}: {existing.get('id')}"
                ],
            )

    vr = validate_hint(hint)
    if not vr.ok:
        return HintResult(False, hint=hint, errors=vr.errors)
    if not dry_run:
        upsert_hint(hint, hints_root)
    return HintResult(True, hint=hint)


def generate_feedback_from_learnings(
    *,
    learnings_root: Path | None = None,
    opportunities_root: Path | None = None,
    hints_root: Path | None = None,
    dry_run: bool = False,
) -> list[HintResult]:
    results: list[HintResult] = []
    learnings = list_learnings(learnings_root)
    for lid in sorted(learnings.keys()):
        lr = learnings[lid]
        text = f"{lr.get('what_failed') or ''} {lr.get('next_signals_hint') or ''}".lower()
        ft = "other"
        if "fail" in text or "kill" in text:
            ft = "failed_experiment"
        elif "audience" in text:
            ft = "audience_signal"
        elif "distribut" in text:
            ft = "distribution_signal"
        results.append(
            create_hint_from_learning(
                lid,
                learnings_root=learnings_root,
                opportunities_root=opportunities_root,
                hints_root=hints_root,
                feedback_type=ft if ft in FEEDBACK_TYPES else "other",
                dry_run=dry_run,
            )
        )
    return results


def _get_hint(hint_id: str, root: Path | None) -> dict[str, Any] | None:
    return list_hints(root).get(hint_id)


def _review(
    hint_id: str,
    to_status: str,
    *,
    reviewed_by: str,
    review_notes: str | None,
    hints_root: Path | None,
    dry_run: bool,
) -> HintResult:
    if not (reviewed_by or "").strip():
        return HintResult(False, errors=["reviewed_by is required for human review"])
    h = _get_hint(hint_id, hints_root)
    if not h:
        return HintResult(False, errors=[f"hint not found: {hint_id}"])
    tr = validate_hint_transition(h.get("status", ""), to_status)
    if not tr.ok:
        return HintResult(False, hint=h, errors=tr.errors)
    now = _now()
    h = {
        **h,
        "status": to_status,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": now,
        "review_notes": (review_notes or "").strip() or None,
        "updated_at": now,
    }
    if not dry_run:
        upsert_hint(h, hints_root)
    return HintResult(True, hint=h)


def approve_hint(
    hint_id: str,
    *,
    reviewed_by: str,
    review_notes: str | None = None,
    hints_root: Path | None = None,
    dry_run: bool = False,
) -> HintResult:
    """proposed → approved. Does NOT create a Signal."""
    return _review(
        hint_id,
        "approved",
        reviewed_by=reviewed_by,
        review_notes=review_notes,
        hints_root=hints_root,
        dry_run=dry_run,
    )


def reject_hint(
    hint_id: str,
    *,
    reviewed_by: str = "human",
    review_notes: str | None = None,
    hints_root: Path | None = None,
    dry_run: bool = False,
) -> HintResult:
    return _review(
        hint_id,
        "rejected",
        reviewed_by=reviewed_by,
        review_notes=review_notes,
        hints_root=hints_root,
        dry_run=dry_run,
    )


def defer_hint(
    hint_id: str,
    *,
    reviewed_by: str = "human",
    review_notes: str | None = None,
    hints_root: Path | None = None,
    dry_run: bool = False,
) -> HintResult:
    return _review(
        hint_id,
        "deferred",
        reviewed_by=reviewed_by,
        review_notes=review_notes,
        hints_root=hints_root,
        dry_run=dry_run,
    )


def _build_candidate(h: dict[str, Any]) -> RawSignalCandidate:
    raw_text = (
        f"[Discovery Feedback] {h.get('hint')} "
        f"(from learning {h.get('source_learning_id')}; not automatic market proof)"
    )
    return RawSignalCandidate(
        source="manual",
        raw_text=raw_text,
        captured_at=_now(),
        created_by=h.get("created_by") or "system:discovery_feedback",
        url=None,
        meta={
            "source_detail": "discovery_feedback",
            "discovery_hint_id": h["id"],
            "source_learning_id": h.get("source_learning_id"),
            "source_opportunity_id": h.get("opportunity_id"),
            "feedback_type": h.get("feedback_type"),
            "provenance": "human_approved_discovery_feedback",
        },
    )


def convert_to_signal(
    hint_id: str,
    *,
    hints_root: Path | None = None,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    dry_run: bool = False,
) -> HintResult:
    """approved → converted + Signal via Phase 2. Idempotent if already converted."""
    h = _get_hint(hint_id, hints_root)
    if not h:
        return HintResult(False, errors=[f"hint not found: {hint_id}"])

    if h.get("status") in ("converted", "accepted") and h.get("converted_signal_id"):
        sig = list_signals(signals_root).get(h["converted_signal_id"])
        return HintResult(True, hint=h, signal=sig)

    if h.get("status") != "approved":
        return HintResult(
            False,
            hint=h,
            errors=[
                f"convert requires status 'approved' (got {h.get('status')!r}); "
                "proposed feedback cannot become a Signal without human approval"
            ],
        )

    oid = h.get("opportunity_id")
    if oid not in list_opportunities(opportunities_root):
        return HintResult(False, hint=h, errors=[f"opportunity not found: {oid}"])

    candidate = _build_candidate(h)
    outcome = process_candidate(candidate, store_root=signals_root, dry_run=dry_run)
    if outcome.get("status") not in ("accepted", "duplicate"):
        return HintResult(
            False,
            hint=h,
            errors=list(outcome.get("errors") or [f"signal ingest status={outcome.get('status')}"]),
        )
    sig = outcome.get("signal")
    if not sig:
        return HintResult(False, hint=h, errors=["signal missing from process_candidate"])

    # Ensure provenance meta
    meta = dict(sig.get("meta") or {})
    meta.update(candidate.meta or {})
    sig = {**sig, "meta": meta}

    tr = validate_hint_transition("approved", "converted")
    if not tr.ok:
        return HintResult(False, hint=h, errors=tr.errors)

    # Prefer "converted"; legacy accept_hint maps to "accepted" for older tests
    final_status = "converted"
    updated = {
        **h,
        "status": final_status,
        "converted_signal_id": sig["id"],
        "updated_at": _now(),
    }
    if not dry_run:
        from discovery.store import upsert_signal

        upsert_signal(sig, signals_root)
        upsert_hint(updated, hints_root)
    return HintResult(True, hint=updated, signal=sig)


def accept_hint(
    hint_id: str,
    *,
    hints_root: Path | None = None,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    reviewed_by: str = "human",
    review_notes: str | None = "legacy accept = approve + convert",
    dry_run: bool = False,
) -> HintResult:
    """Legacy convenience: approve then convert. Prefer approve_hint + convert_to_signal."""
    h = _get_hint(hint_id, hints_root)
    if not h:
        return HintResult(False, errors=[f"hint not found: {hint_id}"])

    if h.get("status") == "proposed":
        ar = approve_hint(
            hint_id,
            reviewed_by=reviewed_by,
            review_notes=review_notes,
            hints_root=hints_root,
            dry_run=dry_run,
        )
        if not ar.ok:
            return ar
        if dry_run:
            # In dry-run approve is not persisted; synthesize approved for convert dry path
            h = {**(ar.hint or h), "status": "approved"}
            # temporarily upsert for convert dry? better: inline convert logic
            candidate = _build_candidate(h)
            outcome = process_candidate(candidate, store_root=signals_root, dry_run=True)
            sig = outcome.get("signal")
            if outcome.get("status") not in ("accepted", "duplicate") or not sig:
                return HintResult(
                    False,
                    hint=h,
                    errors=list(outcome.get("errors") or ["dry-run signal build failed"]),
                )
            meta = dict(sig.get("meta") or {})
            meta.update(candidate.meta or {})
            sig = {**sig, "meta": meta}
            updated = {
                **h,
                "status": "accepted",
                "converted_signal_id": sig["id"],
                "updated_at": _now(),
            }
            return HintResult(True, hint=updated, signal=sig)
        cr = convert_to_signal(
            hint_id,
            hints_root=hints_root,
            signals_root=signals_root,
            opportunities_root=opportunities_root,
            dry_run=False,
        )
        if cr.ok and cr.hint:
            # legacy terminal status name
            legacy = {**cr.hint, "status": "accepted"}
            if not dry_run:
                upsert_hint(legacy, hints_root)
            return HintResult(True, hint=legacy, signal=cr.signal)
        return cr

    if h.get("status") == "approved":
        cr = convert_to_signal(
            hint_id,
            hints_root=hints_root,
            signals_root=signals_root,
            opportunities_root=opportunities_root,
            dry_run=dry_run,
        )
        if cr.ok and cr.hint and not dry_run:
            legacy = {**cr.hint, "status": "accepted"}
            upsert_hint(legacy, hints_root)
            return HintResult(True, hint=legacy, signal=cr.signal)
        return cr

    return HintResult(
        False,
        hint=h,
        errors=[f"cannot accept from status {h.get('status')!r}"],
    )
