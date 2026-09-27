"""Lexical normalization for deterministic similarity (no LLM)."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# Minimal bilingual stopword set — transparency over completeness
_STOP = frozenset(
    """
    a an the and or of to in on for with from by is are was were be been being
    this that these those it its as at into about over under again further then
    once here there when where why how all any both each few more most other some
    such no nor not only own same so than too very can will just should now
    من في على إلى عن مع هذا هذه ذلك تلك التي الذي ما لا لم لن قد كان تكون يكون
    أو و ثم أيضا بين لدى عبر حتى حيث كما أن إن كانا كانوا تكونوا هي هو هم
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9\u0600-\u06ff]+", re.IGNORECASE)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text)).lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def tokenize(text: str | None) -> list[str]:
    t = normalize_text(text)
    if not t:
        return []
    tokens = _TOKEN_RE.findall(t)
    out: list[str] = []
    for tok in tokens:
        if len(tok) < 2:
            continue
        if tok in _STOP:
            continue
        out.append(tok)
    return out


def token_set(text: str | None) -> frozenset[str]:
    return frozenset(tokenize(text))


def join_fields(parts: Iterable[str | None]) -> str:
    return " ".join(p for p in parts if p)
