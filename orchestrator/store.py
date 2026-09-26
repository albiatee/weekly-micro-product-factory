"""Git-friendly cycle store."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "data" / "cycles"


def _path(root: Path | None) -> Path:
    return (root or DEFAULT_ROOT) / "index.json"


def load_index(root: Path | None = None) -> dict[str, Any]:
    p = _path(root)
    if not p.exists():
        return {"cycles": {}, "updated_at": None}
    return json.loads(p.read_text(encoding="utf-8"))


def save_index(data: dict[str, Any], root: Path | None = None) -> Path:
    base = root or DEFAULT_ROOT
    base.mkdir(parents=True, exist_ok=True)
    p = _path(root)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)
    return p


def upsert_cycle(cycle: dict[str, Any], root: Path | None = None) -> Path:
    data = load_index(root)
    cycles = data.setdefault("cycles", {})
    cycles[cycle["id"]] = cycle
    from datetime import datetime, timezone

    data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return save_index(data, root)


def get_cycle(cycle_id: str, root: Path | None = None) -> dict[str, Any] | None:
    return (load_index(root).get("cycles") or {}).get(cycle_id)
