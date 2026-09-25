"""Normalize raw candidates into Signal-shaped dicts (no fabricated facts)."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from .quality import apply_quality
from .sources.base import RawSignalCandidate


def generate_signal_id() -> str:
    return f"sig_{uuid.uuid4().hex[:16]}"


def normalize_text_for_dedupe(text: str) -> str:
    """Deterministic fingerprint for exact/near-exact duplicate detection."""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def normalize_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    return u or None


def candidate_to_signal_dict(candidate: RawSignalCandidate, *, signal_id: str | None = None) -> dict[str, Any]:
    """Map candidate → Signal fields. Does not invent market claims."""
    captured = candidate.captured_at
    if not captured or not str(captured).strip():
        captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    source = candidate.source if candidate.source is not None else "manual"
    if isinstance(source, str):
        source = source.strip()
    else:
        source = str(source)

    sig: dict[str, Any] = {
        "id": signal_id or generate_signal_id(),
        "source": source,
        "raw_text": (candidate.raw_text or "").strip(),
        "captured_at": str(captured).strip(),
    }

    if candidate.created_by and str(candidate.created_by).strip():
        sig["created_by"] = str(candidate.created_by).strip()
    if candidate.language and str(candidate.language).strip():
        sig["language"] = str(candidate.language).strip()
    if candidate.geo_hint and str(candidate.geo_hint).strip():
        sig["geo_hint"] = str(candidate.geo_hint).strip()
    url = normalize_url(candidate.url)
    if url:
        sig["url"] = url
    if candidate.meta:
        # provenance only — do not add invented demand metrics
        sig["meta"] = dict(candidate.meta)

    # Phase 2: deterministic quality enrichment (optional fields; backward compatible)
    sig = apply_quality(sig)
    return sig
