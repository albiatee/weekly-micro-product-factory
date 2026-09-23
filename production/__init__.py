"""Phase 6 — Production Bridge (Decision execute → existing product artifacts).

Does not rewrite weekly-build. Does not implement Distribution.
"""
from .bridge import run_production_bridge

__all__ = ["run_production_bridge"]
