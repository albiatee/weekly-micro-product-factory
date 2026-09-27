"""Read-only helpers over Factory JSON stores. Never write."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def project_root() -> Path:
    return ROOT


def _safe_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeError):
        return {"_error": "malformed_or_unreadable", "path": str(path)}
    if not isinstance(data, dict):
        return {"_error": "not_an_object", "path": str(path)}
    return data


def _entities(data: dict[str, Any], key: str) -> dict[str, Any]:
    if data.get("_error"):
        return {}
    raw = data.get(key)
    if isinstance(raw, dict):
        return {k: v for k, v in raw.items() if isinstance(v, dict)}
    # fallback: top-level id-like keys
    return {
        k: v
        for k, v in data.items()
        if k not in ("updated_at",) and isinstance(v, dict) and not k.startswith("_")
    }


def read_index(store_name: str, entity_key: str, root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    path = base / "data" / store_name / "index.json"
    data = _safe_load(path)
    if data.get("_error"):
        return {
            "items": {},
            "count": 0,
            "updated_at": None,
            "store_status": "error",
            "error": data.get("_error"),
        }
    items = _entities(data, entity_key)
    return {
        "items": items,
        "count": len(items),
        "updated_at": data.get("updated_at"),
        "store_status": "ok" if path.exists() else "missing",
    }


def list_products(root: Path | None = None) -> dict[str, Any]:
    base = (root or ROOT) / "products" / "weekly"
    items: dict[str, Any] = {}
    if not base.exists():
        return {"items": {}, "count": 0, "store_status": "missing"}
    for week_dir in sorted(base.iterdir()):
        if not week_dir.is_dir():
            continue
        meta: dict[str, Any] = {}
        meta_path = week_dir / "meta.json"
        if meta_path.exists():
            try:
                loaded = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    meta = loaded
            except (json.JSONDecodeError, OSError):
                meta = {"_error": "malformed_meta"}
        items[week_dir.name] = {
            "week": meta.get("week") or week_dir.name,
            "title": meta.get("title") or week_dir.name,
            "description": meta.get("description") or "",
            "path": meta.get("path") or "",
            "build_method": meta.get("build_method") or "",
            "href": f"/products/weekly/{week_dir.name}/",
            "generated_at": meta.get("generated_at"),
            "diversity_score": meta.get("diversity_score"),
        }
    return {"items": items, "count": len(items), "store_status": "ok"}
