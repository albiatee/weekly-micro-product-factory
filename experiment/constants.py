"""Experiment lifecycle transitions (Phase 4)."""
from __future__ import annotations

EXP_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"running", "aborted"}),
    "running": frozenset({"completed", "aborted"}),
    "completed": frozenset(),
    "aborted": frozenset(),
}

ALLOWED_TYPES = frozenset(
    {
        "smoke_page",
        "waitlist",
        "concierge",
        "preorder",
        "community_vote",
        "manual_pilot",
    }
)
