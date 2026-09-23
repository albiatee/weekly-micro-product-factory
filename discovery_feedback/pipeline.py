"""Discovery Feedback pipeline: Learning → Hint → Human Review → Signal."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analytics.store import list_learnings
from contracts.validate import validate_signal
from discovery.normalize import candidate_to_signal_dict
from discovery.pipeline import process_candidate
from discovery.sources.base import RawSignalCandidate
from discovery.store import list_signals, upsert_signal
from opportunity.store import list_opportunities

from .build import build_hint_from_learning, normalize_hint_text
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
    dry_run: bool = False,
) -> HintResult:
    learnings = list_learnings(learnings_root)
    lr = learnings.get(learning_id)
    if not lr:
        return HintResult(False, errors=[f"learning not found: {learning_id}"])

    oid = lr.get("opportunity_id")
    opps = list_opportunities(opportunities_root)
    if not oid or oid not in opps:
        return HintResult(False, errors=[f"opportunity not found for learning: {oid}"])

    if not (lr.get("next_signals_hint") or "").strip():
        return HintResult(False, errors=["LearningRecord has no next_signals_hint"])

    try:
        hint = build_hint_from_learning(lr, created_by=created_by)
    except ValueError as e:
        return HintResult(False, errors=[str(e)])

    # Dedup: same learning + normalized hint while proposed/accepted
    norm = normalize_hint_text(hint["hint"])
    for existing in list_hints(hints_root).values():
        if existing.get("source_learning_id") != learning_id:
            continue
        if normalize_hint_text(existing.get("hint") or "") != norm:
            continue
        if existing.get("status") in ("proposed", "accepted"):
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


def _get_hint(hint_id: str, root: Path | None) -> dict[str, Any] | None:
    return list_hints(root).get(hint_id)


def reject_hint(
    hint_id: str, *, hints_root: Path | None = None, dry_run: bool = False
) -> HintResult:
    h = _get_hint(hint_id, hints_root)
    if not h:
        return HintResult(False, errors=[f"hint not found: {hint_id}"])
    tr = validate_hint_transition(h.get("status", ""), "rejected")
    if not tr.ok:
        return HintResult(False, hint=h, errors=tr.errors)
    h = {**h, "status": "rejected", "updated_at": _now()}
    if not dry_run:
        upsert_hint(h, hints_root)
    return HintResult(True, hint=h)


def defer_hint(
    hint_id: str, *, hints_root: Path | None = None, dry_run: bool = False
) -> HintResult:
    h = _get_hint(hint_id, hints_root)
    if not h:
        return HintResult(False, errors=[f"hint not found: {hint_id}"])
    tr = validate_hint_transition(h.get("status", ""), "deferred")
    if not tr.ok:
        return HintResult(False, hint=h, errors=tr.errors)
    h = {**h, "status": "deferred", "updated_at": _now()}
    if not dry_run:
        upsert_hint(h, hints_root)
    return HintResult(True, hint=h)


def accept_hint(
    hint_id: str,
    *,
    hints_root: Path | None = None,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    dry_run: bool = False,
) -> HintResult:
    """proposed → accepted only after Signal is validated (and stored unless dry_run).

    Order: validate transition → build Signal → validate Signal →
    (persist Signal then Hint) to avoid accepted-without-signal.
    """
    h = _get_hint(hint_id, hints_root)
    if not h:
        return HintResult(False, errors=[f"hint not found: {hint_id}"])

    tr = validate_hint_transition(h.get("status", ""), "accepted")
    if not tr.ok:
        return HintResult(False, hint=h, errors=tr.errors)

    oid = h.get("opportunity_id")
    if oid not in list_opportunities(opportunities_root):
        return HintResult(False, hint=h, errors=[f"opportunity not found: {oid}"])

    # Build Signal via Phase 2 conventions
    raw_text = (
        f"[Discovery Feedback] {h.get('hint')} "
        f"(from learning {h.get('source_learning_id')}; not automatic market proof)"
    )
    candidate = RawSignalCandidate(
        source="manual",
        raw_text=raw_text,
        captured_at=_now(),
        created_by=h.get("created_by") or "system:discovery_feedback",
        meta={
            "source_detail": "discovery_feedback",
            "discovery_hint_id": h["id"],
            "source_learning_id": h.get("source_learning_id"),
            "opportunity_id": oid,
        },
    )
    signal = candidate_to_signal_dict(candidate)
    # prevent duplicate signal from same accepted hint text path
    existing_sigs = list_signals(signals_root)
    from discovery.dedupe import find_duplicate

    dup = find_duplicate(signal, existing_sigs)
    if dup:
        return HintResult(
            False,
            hint=h,
            signal=existing_sigs.get(dup),
            errors=[f"signal would duplicate existing {dup}; refusing accept"],
        )

    sv = validate_signal(signal)
    if not sv.ok:
        return HintResult(False, hint=h, signal=signal, errors=sv.errors)

    if dry_run:
        return HintResult(True, hint=h, signal=signal)

    # Persist Signal first, then mark hint accepted
    upsert_signal(signal, signals_root)
    h_acc = {
        **h,
        "status": "accepted",
        "updated_at": _now(),
        "resulting_signal_id": signal["id"],
    }
    vr = validate_hint(h_acc)
    if not vr.ok:
        # Signal already written — surface failure clearly (orphan signal possible)
        return HintResult(
            False,
            hint=h_acc,
            signal=signal,
            errors=vr.errors + ["signal was written but hint accept validation failed"],
        )
    upsert_hint(h_acc, hints_root)
    return HintResult(True, hint=h_acc, signal=signal)
