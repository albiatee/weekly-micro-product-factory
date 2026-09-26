"""Persist analytics snapshots under data/analytics/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "analytics"
INDEX_NAME = "index.json"


def store_path(root: Path | None = None) -> Path:
    return (root or DEFAULT_STORE_DIR) / INDEX_NAME


def load_index(root: Path | None = None) -> dict[str, Any]:
    path = store_path(root)
    if not path.exists():
        return {"snapshots": [], "learnings": {}, "updated_at": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("snapshots", [])
    data.setdefault("learnings", {})
    return data


def save_index(data: dict[str, Any], root: Path | None = None) -> Path:
    path = store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def append_snapshot(snapshot: dict[str, Any], root: Path | None = None) -> Path:
    """Persist snapshot. Idempotent for same filter: replace prior matching filter entry."""
    data = load_index(root)
    filt = snapshot.get("filter") or {}
    snaps = list(data.get("snapshots") or [])
    # drop previous snapshots with same opportunity_id filter (keep history length bounded)
    snaps = [s for s in snaps if (s.get("filter") or {}) != filt]
    snaps.append(snapshot)
    data["snapshots"] = snaps
    data["latest_snapshot"] = snapshot
    return save_index(data, root)


def upsert_learning(lr: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    data["learnings"][lr["id"]] = lr
    return save_index(data, root)


def list_learnings(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return load_index(root).get("learnings") or {}
