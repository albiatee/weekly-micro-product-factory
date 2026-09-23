"""Git-friendly distribution storage under data/distribution/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "distribution"
INDEX_NAME = "index.json"


def store_path(root: Path | None = None) -> Path:
    return (root or DEFAULT_STORE_DIR) / INDEX_NAME


def load_index(root: Path | None = None) -> dict[str, Any]:
    path = store_path(root)
    if not path.exists():
        return {"plans": {}, "actions": {}, "updated_at": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("plans", {})
    data.setdefault("actions", {})
    if not isinstance(data["plans"], dict):
        data["plans"] = {}
    if not isinstance(data["actions"], dict):
        data["actions"] = {}
    return data


def save_index(data: dict[str, Any], root: Path | None = None) -> Path:
    path = store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def list_plans(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return load_index(root).get("plans") or {}


def list_actions(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return load_index(root).get("actions") or {}


def upsert_plan(plan: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    data["plans"][plan["id"]] = plan
    return save_index(data, root)


def upsert_action(action: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    data["actions"][action["id"]] = action
    return save_index(data, root)
