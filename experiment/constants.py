"""Experiment lifecycle transitions and types (Phase 4)."""
from __future__ import annotations

from contracts.constants import EXPERIMENT_TYPES

EXP_TRANSITIONS: dict[str, frozenset[str]] = {
    "planned": frozenset({"running", "aborted"}),
    "running": frozenset({"completed", "aborted"}),
    "completed": frozenset(),
    "aborted": frozenset(),
}

# Alias for local use — single source of truth is contracts
ALLOWED_TYPES = EXPERIMENT_TYPES

# Fields frozen after any results/observations are recorded
IMMUTABLE_AFTER_RESULTS = frozenset(
    {
        "hypothesis_test",
        "measurement_plan",
        "success_criteria",
        "failure_criteria",
        "success_threshold",
        "target_population",
        "experiment_type",
        "assumptions_tested",
    }
)
