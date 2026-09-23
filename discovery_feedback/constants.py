"""Discovery Hint statuses and transitions (Phase 9)."""
from __future__ import annotations

HINT_STATUSES = frozenset({"proposed", "accepted", "rejected", "deferred"})

HINT_TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"accepted", "rejected", "deferred"}),
    "accepted": frozenset(),
    "rejected": frozenset(),
    "deferred": frozenset(),
}
