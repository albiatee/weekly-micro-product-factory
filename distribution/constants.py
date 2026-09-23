"""Distribution contracts — Phase 7."""
from __future__ import annotations

PLAN_STATUSES = frozenset(
    {"planned", "ready", "running", "completed", "paused", "cancelled"}
)

PLAN_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"ready", "running", "cancelled"}),
    "ready": frozenset({"running", "cancelled", "paused"}),
    "running": frozenset({"completed", "paused", "cancelled"}),
    "paused": frozenset({"running", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

CHANNELS = frozenset(
    {
        "github",
        "telegram",
        "reddit",
        "x",
        "direct",
        "seo",
        "community",
        "other",
    }
)

ACTION_TYPES = frozenset(
    {
        "publish",
        "announce",
        "submit",
        "share",
        "manual_post",
        "other",
    }
)

ACTION_STATUSES = frozenset({"planned", "executed", "failed", "cancelled"})
