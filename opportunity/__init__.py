"""Phase 3 — Opportunity Engine (Signals → hypothesized Opportunities).

Does not create Experiments, Decisions, or touch production.
"""
from .pipeline import generate_from_store, generate_from_signal_ids

__all__ = ["generate_from_store", "generate_from_signal_ids"]
