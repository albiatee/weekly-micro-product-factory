"""Phase 5 — Decision Gate (Experiment evidence → explicit Decision).

Does not trigger production or auto-pick winners from scores.
"""
from .pipeline import create_decision

__all__ = ["create_decision"]
