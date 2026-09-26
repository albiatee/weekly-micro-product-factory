"""Distribution contracts — Phase 7."""
from __future__ import annotations

# Lifecycle: planned → prepared → published | failed | cancelled
# Legacy aliases kept for backward compatibility with earlier V2 tests:
#   ready ≈ prepared, running ≈ in-progress prep, completed ≈ published
PLAN_STATUSES = frozenset(
    {
        "planned",
        "prepared",
        "ready",  # legacy synonym of prepared
        "running",  # legacy in-progress
        "published",
        "completed",  # legacy synonym of published
        "failed",
        "paused",
        "cancelled",
    }
)

PLAN_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"prepared", "ready", "running", "cancelled"}),
    "prepared": frozenset({"published", "failed", "cancelled", "running"}),
    "ready": frozenset({"running", "published", "cancelled", "paused"}),
    "running": frozenset({"completed", "published", "failed", "paused", "cancelled"}),
    "paused": frozenset({"running", "cancelled"}),
    "published": frozenset(),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}

CHANNELS = frozenset(
    {
        # Phase 7 preferred
        "own_site",
        "landing_page",
        "product_catalog",
        "community_post",
        "social_post",
        "email",
        # Legacy / existing
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

DISTRIBUTION_TYPES = frozenset(
    {
        "plan",
        "announcement",
        "listing",
        "share",
        "manual",
    }
)

ACTION_TYPES = frozenset(
    {
        "publish",
        "announce",
        "submit",
        "share",
        "manual_post",
        "prepare",
        "other",
    }
)

ACTION_STATUSES = frozenset({"planned", "executed", "failed", "cancelled"})
