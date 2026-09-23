"""Signal Discovery pipeline: collect → normalize → validate → dedupe → store."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from contracts.validate import validate_signal

from .dedupe import find_duplicate
from .normalize import candidate_to_signal_dict
from .sources.base import RawSignalCandidate
from .sources.manual import ManualSignalSource
from .store import list_signals, upsert_signal


@dataclass
class IngestResult:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    duplicates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.rejected) == 0 and len(self.duplicates) == 0


def process_candidate(
    candidate: RawSignalCandidate,
    *,
    store_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process one candidate. Returns status payload."""
    signal = candidate_to_signal_dict(candidate)
    vr = validate_signal(signal)
    if not vr.ok:
        return {"status": "rejected", "errors": vr.errors, "signal": signal}

    existing = list_signals(store_root)
    dup_id = find_duplicate(signal, existing)
    if dup_id:
        return {
            "status": "duplicate",
            "duplicate_of": dup_id,
            "reason": "normalized text or URL matches existing signal",
            "signal": signal,
        }

    if not dry_run:
        upsert_signal(signal, store_root)
    return {"status": "accepted", "signal": signal}


def ingest_candidates(
    candidates: list[RawSignalCandidate],
    *,
    store_root: Path | None = None,
    dry_run: bool = False,
) -> IngestResult:
    result = IngestResult()
    # Process sequentially so later candidates see earlier accepts in-store
    for cand in candidates:
        outcome = process_candidate(cand, store_root=store_root, dry_run=dry_run)
        if outcome["status"] == "accepted":
            result.accepted.append(outcome)
            if dry_run:
                # keep in-memory set for multi-item dry_run dedupe
                pass
        elif outcome["status"] == "duplicate":
            result.duplicates.append(outcome)
        else:
            result.rejected.append(outcome)
    return result


def ingest_manual_payload(
    items: list[dict[str, Any]] | dict[str, Any],
    *,
    store_root: Path | None = None,
    dry_run: bool = False,
) -> IngestResult:
    if isinstance(items, dict):
        # single object or {"signals": [...]}
        if "signals" in items and isinstance(items["signals"], list):
            items = items["signals"]
        else:
            items = [items]
    source = ManualSignalSource(list(items))
    return ingest_candidates(source.collect(), store_root=store_root, dry_run=dry_run)


def ingest_manual_file(
    path: Path | str,
    *,
    store_root: Path | None = None,
    dry_run: bool = False,
) -> IngestResult:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".jsonl":
        items = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    else:
        data = json.loads(text)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("signals"), list):
            items = data["signals"]
        else:
            items = [data]
    return ingest_manual_payload(items, store_root=store_root, dry_run=dry_run)
