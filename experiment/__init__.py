"""Phase 4 — Validation Experiments (Opportunity → measurable experiment).

Does not create Decisions or touch production.
"""
from .pipeline import (
    abort_experiment,
    complete_experiment,
    create_experiment,
    record_results,
    start_experiment,
)

__all__ = [
    "create_experiment",
    "start_experiment",
    "record_results",
    "complete_experiment",
    "abort_experiment",
]
