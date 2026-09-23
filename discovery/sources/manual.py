"""Manual signal ingestion — no API keys required."""
from __future__ import annotations

from typing import Any

from .base import RawSignalCandidate, SignalSource


class ManualSignalSource(SignalSource):
    """Build candidates from structured dicts / JSON objects."""

    name = "manual"

    def __init__(self, items: list[dict[str, Any]] | None = None):
        self._items = items or []

    def collect(self) -> list[RawSignalCandidate]:
        out: list[RawSignalCandidate] = []
        for item in self._items:
            if not isinstance(item, dict):
                continue
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            if "source" in item and item["source"] is not None:
                source = str(item["source"]).strip()
            else:
                source = "manual"
            out.append(
                RawSignalCandidate(
                    source=source,
                    raw_text=str(item.get("raw_text") or ""),
                    captured_at=item.get("captured_at"),
                    created_by=item.get("created_by"),
                    language=item.get("language"),
                    geo_hint=item.get("geo_hint"),
                    url=item.get("url"),
                    meta=dict(meta),
                )
            )
        return out
