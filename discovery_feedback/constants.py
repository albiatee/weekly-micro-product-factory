"""Discovery Feedback statuses and transitions (Phase 9)."""
from __future__ import annotations

# proposed → approved | rejected | deferred
# approved → converted (after explicit Signal conversion)
# Legacy "accepted" treated as synonym of converted (approved + signal created)
HINT_STATUSES = frozenset(
    {
        "proposed",
        "approved",
        "rejected",
        "deferred",
        "converted",
        "accepted",  # legacy alias for converted
    }
)

HINT_TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset({"approved", "rejected", "deferred"}),
    "approved": frozenset({"converted", "rejected"}),
    "converted": frozenset(),
    "accepted": frozenset(),  # terminal legacy
    "rejected": frozenset(),
    "deferred": frozenset(),
}

FEEDBACK_TYPES = frozenset(
    {
        "source_gap",
        "recurring_problem",
        "failed_experiment",
        "successful_pattern",
        "distribution_signal",
        "audience_signal",
        "product_signal",
        "other",
    }
)

ACTIVE_FOR_DEDUP = frozenset({"proposed", "approved", "accepted", "converted"})
