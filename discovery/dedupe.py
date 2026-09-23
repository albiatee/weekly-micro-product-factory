"""Basic deterministic deduplication — not semantic clustering."""
from __future__ import annotations

from typing import Any

from .normalize import normalize_text_for_dedupe, normalize_url


def fingerprint(signal: dict[str, Any]) -> str:
    """Stable fingerprint for duplicate detection."""
    text_key = normalize_text_for_dedupe(str(signal.get("raw_text") or ""))
    url = normalize_url(signal.get("url"))
    if url:
        return f"url:{url.lower()}"
    return f"text:{text_key}"


def find_duplicate(
    candidate: dict[str, Any], existing: dict[str, dict[str, Any]]
) -> str | None:
    """Return id of existing signal if duplicate, else None."""
    fp = fingerprint(candidate)
    if fp in ("text:", "url:"):
        return None
    for sid, sig in existing.items():
        if fingerprint(sig) == fp:
            return sid
    return None
