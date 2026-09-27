"""Build read-only searchable documents from real Factory stores."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.normalize import join_fields, token_set

ROOT = Path(__file__).resolve().parents[1]


def _load_items(store: str, key: str, root: Path) -> dict[str, Any]:
    path = root / "data" / store / "index.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    raw = data.get(key)
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, dict)}
    return {}


def _doc(
    *,
    entity_type: str,
    entity_id: str,
    text: str,
    summary: str,
    source: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tokens = token_set(text)
    d: dict[str, Any] = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "text": text,
        "summary": summary,
        "source": source,
        "tokens": sorted(tokens),
        "token_count": len(tokens),
    }
    if extra:
        d["extra"] = extra
    return d


def build_corpus(root: Path | None = None) -> list[dict[str, Any]]:
    """Materialize searchable docs from on-disk stores (read-only)."""
    root = root or ROOT
    docs: list[dict[str, Any]] = []

    for sid, s in _load_items("signals", "signals", root).items():
        text = join_fields(
            [
                s.get("raw_text"),
                s.get("problem_statement"),
                s.get("intent_type"),
                (s.get("meta") or {}).get("sector") if isinstance(s.get("meta"), dict) else None,
            ]
        )
        docs.append(
            _doc(
                entity_type="signal",
                entity_id=sid,
                text=text,
                summary=(s.get("problem_statement") or s.get("raw_text") or "")[:240],
                source=s.get("url") or s.get("source"),
                extra={
                    "qualification_status": s.get("qualification_status"),
                    "intent_type": s.get("intent_type"),
                    "evidence_strength": s.get("evidence_strength"),
                },
            )
        )

    for oid, o in _load_items("opportunities", "opportunities", root).items():
        text = join_fields(
            [
                o.get("title"),
                o.get("problem"),
                o.get("problem_statement"),
                o.get("audience"),
                o.get("value_proposition"),
                o.get("hypothesis"),
                o.get("solution_type"),
            ]
        )
        docs.append(
            _doc(
                entity_type="opportunity",
                entity_id=oid,
                text=text,
                summary=(o.get("title") or o.get("problem") or "")[:240],
                source=",".join(o.get("signal_ids") or []) or None,
                extra={
                    "status": o.get("status"),
                    "signal_ids": o.get("signal_ids") or [],
                    "solution_type": o.get("solution_type"),
                },
            )
        )

    for eid, e in _load_items("experiments", "experiments", root).items():
        text = join_fields(
            [
                e.get("hypothesis"),
                e.get("experiment_type"),
                e.get("status"),
                str(e.get("success_criteria") or ""),
                str(e.get("failure_criteria") or ""),
            ]
        )
        docs.append(
            _doc(
                entity_type="experiment",
                entity_id=eid,
                text=text,
                summary=(e.get("hypothesis") or e.get("id") or "")[:240],
                source=e.get("opportunity_id"),
                extra={
                    "status": e.get("status"),
                    "opportunity_id": e.get("opportunity_id"),
                    "has_results": bool(e.get("results")),
                },
            )
        )

    for did, d in _load_items("decisions", "decisions", root).items():
        text = join_fields(
            [
                d.get("verdict"),
                d.get("reason"),
                d.get("opportunity_id"),
                d.get("experiment_id"),
            ]
        )
        docs.append(
            _doc(
                entity_type="decision",
                entity_id=did,
                text=text,
                summary=(d.get("reason") or d.get("verdict") or "")[:240],
                source=d.get("opportunity_id"),
                extra={
                    "verdict": d.get("verdict"),
                    "decided_by": d.get("decided_by"),
                    "opportunity_id": d.get("opportunity_id"),
                },
            )
        )

    # learning records — try common keys
    for key in ("learnings", "learning_records", "records"):
        learnings = _load_items("analytics", key, root)
        if learnings:
            for lid, lr in learnings.items():
                text = join_fields(
                    [
                        lr.get("summary"),
                        lr.get("insight"),
                        lr.get("lesson"),
                        lr.get("notes"),
                        str(lr.get("outcome") or ""),
                    ]
                )
                docs.append(
                    _doc(
                        entity_type="learning",
                        entity_id=lid,
                        text=text,
                        summary=(lr.get("summary") or lr.get("insight") or "")[:240],
                        source=lr.get("opportunity_id") or lr.get("experiment_id"),
                        extra={"outcome": lr.get("outcome")},
                    )
                )
            break

    # products from filesystem
    weekly = root / "products" / "weekly"
    if weekly.exists():
        for week_dir in sorted(weekly.iterdir()):
            if not week_dir.is_dir():
                continue
            meta: dict[str, Any] = {}
            mp = week_dir / "meta.json"
            if mp.exists():
                try:
                    loaded = json.loads(mp.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        meta = loaded
                except (json.JSONDecodeError, OSError):
                    meta = {}
            text = join_fields(
                [
                    meta.get("title"),
                    meta.get("description"),
                    meta.get("path"),
                    meta.get("week"),
                    meta.get("build_method"),
                ]
            )
            docs.append(
                _doc(
                    entity_type="product",
                    entity_id=week_dir.name,
                    text=text,
                    summary=(meta.get("title") or week_dir.name)[:240],
                    source=f"products/weekly/{week_dir.name}/",
                    extra={
                        "week": meta.get("week") or week_dir.name,
                        "build_method": meta.get("build_method"),
                        "href": f"../products/weekly/{week_dir.name}/",
                    },
                )
            )

    return docs
