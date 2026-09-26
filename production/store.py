"""Git-friendly Production Specification storage under data/production/."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "production"
INDEX_NAME = "index.json"


def store_path(root: Path | None = None) -> Path:
    return (root or DEFAULT_STORE_DIR) / INDEX_NAME


def load_index(root: Path | None = None) -> dict[str, Any]:
    path = store_path(root)
    if not path.exists():
        return {"production_specs": {}, "updated_at": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    if "production_specs" not in data or not isinstance(data["production_specs"], dict):
        data["production_specs"] = {}
    return data


def save_index(data: dict[str, Any], root: Path | None = None) -> Path:
    path = store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def list_production_specs(root: Path | None = None) -> dict[str, dict[str, Any]]:
    return load_index(root).get("production_specs") or {}


def upsert_production_spec(spec: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    data["production_specs"][spec["id"]] = spec
    return save_index(data, root)


def get_production_spec(spec_id: str, root: Path | None = None) -> dict[str, Any] | None:
    return list_production_specs(root).get(spec_id)
