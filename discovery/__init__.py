"""Phase 2 — Signal Discovery (collect → normalize → validate → store).

Does not create Opportunities or touch production workflows.
"""
from .pipeline import ingest_manual_payload, ingest_manual_file

__all__ = ["ingest_manual_payload", "ingest_manual_file"]
