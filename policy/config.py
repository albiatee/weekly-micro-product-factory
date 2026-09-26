"""Load orchestrator/policy configuration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "config" / "orchestrator_v0.json"

_DEFAULTS: dict[str, Any] = {
    "orchestrator_enabled": False,
    "policy_id": "policy_autonomous_factory_v0",
    "policy_version": "0.1.0",
    "allowed_templates": ["static_html_microproduct"],
    "allowed_channels": ["github_pages"],
    "allowed_source_keys": ["manual", "other"],
    "max_opportunities_per_cycle": 1,
    "max_experiments_per_cycle": 1,
    "max_iterations_per_opportunity": 2,
    "max_publishes_per_cycle": 1,
    "max_publishes_per_week": 3,
    "max_spend_per_cycle": 0,
    "max_spend_per_week": 0,
    "max_risk": 0.5,
    "minimum_qualified_source_count": 1,
    "auto_feedback_convert": False,
    "collect_on_cycle": False,
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_CONFIG_PATH
    data = dict(_DEFAULTS)
    if p.exists():
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    return data
