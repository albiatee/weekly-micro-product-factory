"""Git-friendly Opportunity storage under data/opportunities/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "opportunities"
INDEX_NAME = "index.json"


def store_path(root: Path | None = None) -> Path:
    return (root or DEFAULT_STORE_DIR) / INDEX_NAME


def load_index(root: Path | None = None) -> dict[str, Any]:
    path = store_path(root)
    if not path.exists():
        return {"opportunities": {}, "updated_at": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "opportunities" not in data or not isinstance(data["opportunities"], dict):
        data["opportunities"] = {}
    return data


def save_index(data: dict[str, Any], root: Path | None = None) -> Path:
    path = store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def list_opportunities(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return load_index(root).get("opportunities") or {}


def upsert_opportunity(opp: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    data["opportunities"][opp["id"]] = opp
    return save_index(data, root)
