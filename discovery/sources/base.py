"""Source abstraction for future collectors (GitHub, X, Reddit, …)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawSignalCandidate:
    """Pre-contract candidate from a source. IDs are assigned later."""

    source: str
    raw_text: str
    captured_at: str | None = None
    created_by: str | None = None
    language: str | None = None
    geo_hint: str | None = None
    url: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class SignalSource(ABC):
    """Interface for signal collectors. Phase 2: ManualSignalSource only."""

    name: str = "base"

    @abstractmethod
    def collect(self) -> list[RawSignalCandidate]:
        """Return raw candidates (not yet validated Signals)."""
