"""System kill switch — above Policy."""
from __future__ import annotations

import os
from typing import Any


def is_enabled(config: dict[str, Any], *, env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else dict(os.environ)
    raw = env.get("ORCHESTRATOR_ENABLED")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(config.get("orchestrator_enabled", False))
