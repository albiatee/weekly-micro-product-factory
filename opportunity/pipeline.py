"""Opportunity Engine pipeline: load signals → generate → validate → dedupe → store."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contracts.validate import validate_opportunity

from discovery.quality import apply_quality, is_opportunity_eligible
from discovery.store import list_signals as list_stored_signals

from .dedupe import find_duplicate
from .generate import build_opportunity_from_signals
from .store import list_opportunities, upsert_opportunity


@dataclass
class GenerateResult:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.rejected) == 0


def _resolve_signals(
    signal_ids: list[str],
    signals_map: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    found: list[dict[str, Any]] = []
    missing: list[str] = []
    for sid in signal_ids:
        if sid in signals_map:
            found.append(signals_map[sid])
        else:
            missing.append(sid)
    return found, missing


def generate_from_signal_ids(
    signal_ids: list[str],
    *,
    signals_map: dict[str, dict[str, Any]] | None = None,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    created_by: str = "system:opportunity_engine",
    combine: bool = False,
    dry_run: bool = False,
) -> GenerateResult:
    """Generate hypothesized Opportunities from signal ids.

    combine=False: one Opportunity per signal id
    combine=True: one Opportunity from all listed signals together
    """
    result = GenerateResult()
    if signals_map is None:
        signals_map = list_stored_signals(signals_root)

    if not signal_ids:
        result.rejected.append(
            {"status": "rejected", "errors": ["no signal_ids provided"], "opportunity": None}
        )
        return result

    if combine:
        batches = [signal_ids]
    else:
        batches = [[sid] for sid in signal_ids]

    existing = list_opportunities(opportunities_root)

    for batch in batches:
        found, missing = _resolve_signals(batch, signals_map)
        if missing or not found:
            result.rejected.append(
                {
                    "status": "rejected",
                    "errors": [f"missing or empty signals: {missing or batch}"],
                    "signal_ids": batch,
                }
            )
            continue

        # Phase 2: only qualified demand-side signals may form Opportunities
        ineligible = []
        enriched = []
        for s in found:
            s2 = apply_quality(dict(s))
            enriched.append(s2)
            if not is_opportunity_eligible(s2):
                ineligible.append(
                    {
                        "id": s2.get("id"),
                        "intent_type": s2.get("intent_type"),
                        "qualification_status": s2.get("qualification_status"),
                        "evidence_strength": s2.get("evidence_strength"),
                    }
                )
        if ineligible:
            result.rejected.append(
                {
                    "status": "rejected",
                    "errors": [
                        "signal quality gate: not qualified for opportunity generation"
                    ],
                    "signal_ids": batch,
                    "quality": ineligible,
                }
            )
            continue

        try:
            opp = build_opportunity_from_signals(enriched, created_by=created_by)
        except ValueError as e:
            result.rejected.append({"status": "rejected", "errors": [str(e)], "signal_ids": batch})
            continue

        vr = validate_opportunity(opp)
        if not vr.ok:
            result.rejected.append(
                {"status": "rejected", "errors": vr.errors, "opportunity": opp}
            )
            continue

        dup = find_duplicate(opp, existing)
        if dup:
            result.duplicates.append(
                {
                    "status": "duplicate",
                    "duplicate_of": dup,
                    "reason": "same signal set or normalized problem",
                    "opportunity": opp,
                }
            )
            continue

        if not dry_run:
            upsert_opportunity(opp, opportunities_root)
            existing[opp["id"]] = opp
        result.accepted.append({"status": "accepted", "opportunity": opp})

    return result


def generate_from_store(
    *,
    signals_root: Path | None = None,
    opportunities_root: Path | None = None,
    created_by: str = "system:opportunity_engine",
    combine_all: bool = False,
    dry_run: bool = False,
) -> GenerateResult:
    """Generate opportunities from all stored signals."""
    signals_map = list_stored_signals(signals_root)
    ids = list(signals_map.keys())
    return generate_from_signal_ids(
        ids,
        signals_map=signals_map,
        signals_root=signals_root,
        opportunities_root=opportunities_root,
        created_by=created_by,
        combine=combine_all,
        dry_run=dry_run,
    )
